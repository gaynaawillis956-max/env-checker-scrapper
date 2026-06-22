package paths

import (
	"bufio"
	_ "embed"
	"sort"
	"strings"
	"sync"
)

//go:embed wordlist.txt
var wordlistData string

var (
	once   sync.Once
	cached []string
)

// Build returns the deduplicated list of scan paths (1700+ variants).
func Build() []string {
	once.Do(func() {
		cached = generatePaths()
	})
	return cached
}

func generatePaths() []string {
	set := make(map[string]struct{}, 4096)
	add := func(values ...string) {
		for _, v := range values {
			if v == "" {
				continue
			}
			normalized := normalizePath(v)
			set[normalized] = struct{}{}
		}
	}

	baseEnvs := []string{
		".env", ".env.example", ".env.sample", ".env.template", ".env.backup", ".env.bak", ".env.old", ".env.orig",
		".env.local", ".env.dev", ".env.development", ".env.prod", ".env.production", ".env.stage", ".env.staging",
		".env.test", ".env.qa", ".env.copy", ".env.save", ".env.save~", ".env.tmp", ".env.temp", ".env.release",
		".env.debug", ".env.deploy", ".env1", ".env2", ".env.default", ".env.hidden", ".env.disabled", ".env.cache",
	}

	baseConfigs := []string{
		"config.env", "config/.env", "config/.env.local", "config/.env.production", "config.php.bak", "config.php.save",
		"config.php.old", "config.php.previous", "config.php.save~", "config.json", "config.yml", "config.yaml",
		"config/.env.dev", "config/settings/.env", "settings/.env", "settings/local/.env", "settings/production/.env",
		"settings/test/.env",
	}

	// Mail / SMTP-specific config paths developers commonly leave exposed
	mailPaths := []string{
		".env.mail", ".env.smtp", ".env.email", ".env.mailer",
		"mail.env", "smtp.env", "email.env",
		"config/mail.php", "config/email.php", "config/smtp.php",
		"app/config/mail.php", "application/config/email.php",
		".sendgrid.env", ".mailgun.env", ".postmark.env",
		"config/services.php",                         // Laravel: contains mail/SES keys
		"config/mail.yml", "config/mailer.yml",        // Symfony mailer
		".env.mailer", "mailer.env",
		"config/mailers.yml",                          // Rails ActionMailer
		"config/environments/production.rb",           // Rails sometimes has SMTP inline
		"application.properties", "application.yml",   // Spring Boot SMTP config
		"application-prod.properties", "application-prod.yml",
	}

	gitPaths := []string{
		".git/config", ".git/HEAD", ".git/config.lock", ".git/credentials", ".git-credentials", ".gitmodules", ".gitignore",
		".git/info/exclude", ".git/refs/heads/master", ".git/refs/heads/main", ".git/logs/HEAD",
	}

	cloudPaths := []string{
		".aws/credentials", ".aws/config", ".aws/credentials.bak", ".aws/credentials.save", "aws/credentials", "aws/.env",
		"aws/braket/.env.quantum", "aws/bedrock/.env", "aws/sagemaker/.env", "aws/lambda/.env", "aws/secretsmanager/.env",
		".azure/credentials", ".azure/config", "azure/.env", "azure/devops/.env", "azure/pipelines/.env", "azure/keyvault/.env",
		".gcp/credentials", ".gcp/secrets", "gcp/.env", "gcp/functions/.env", "gcp/appengine/.env", "gcp/cloudrun/.env",
		"cloud/.env", "cloud/config/.env", "cloud/prod/.env", "cloud/secrets/.env", "cloud/dev/.env",
	}

	terraPaths := []string{
		"terraform.tfstate", "terraform.tfstate.backup", ".terraform/terraform.tfstate", ".terraform/terraform.tfstate.backup",
		"terraform/.terraform.tfstate", "terraform/.terraform.tfstate.backup", "terraform.tfvars", "terraform.tfvars.json",
		"terraform/state/default.tfstate", "terraform/environments/prod/terraform.tfstate", "terraform/environments/dev/terraform.tfstate",
		"terraform/workspaces/default/terraform.tfstate", "terraform/live/us-east-1/terraform.tfstate",
	}

	dockerPaths := []string{
		"docker-compose.yml", "docker-compose.yaml", "docker-compose.override.yml", "docker-compose.dev.yml",
		"docker-compose.prod.yml", "docker-compose.test.yml", "docker-compose.local.yml", "docker-compose.ci.yml",
		"docker/.env", "docker/dev/.env", "docker/prod/.env", "docker/staging/.env", "docker/test/.env",
		"docker/kubernetes/.env", "docker/swarm/.env", "docker-compose/.env", "compose/.env", "compose/prod/.env", "compose/dev/.env",
	}

	encodedPaths := []string{
		"%2eenv", "%2e%2e%2f.env", "%2f%2eenv", "%2f.git%2fconfig", "%2f%2eaws%2fcredentials", "%252eenv", "%255c.env",
		"..%2f.env", "..%252f.env", "..%255c.env",
	}

	// Backup / leftover files — editors and sysadmins leave these in web roots
	backupPaths := []string{
		".env~", ".env.swp", ".env.swo", ".env.bkp", ".env.bck",
		"env.txt", "env.bak", "env.zip", "env.tar.gz",
		".env.php", "env.php", // PHP wrappers that sometimes expose raw text
		"web.config.bak", "web.config.old",
		"wp-config.php.bak", "wp-config.php.save", "wp-config.php.swp",
		"wp-config.php.orig", "wp-config.php.old", "wp-config.php~",
		"wp-config-sample.php", "wp-config.txt",
		"local_settings.py", "local_settings.py.bak",
		"settings.py.bak", "settings_local.py",
		"database.yml", "database.yml.bak", "database.yml.example",
		"secrets.yml", "secrets.yml.key", "master.key",
		"credentials.yml.enc", "config/master.key",
	}

	// CI/CD pipeline files — often contain API tokens, deploy keys, SMTP vars
	cicdPaths := []string{
		".travis.yml", ".travis.yaml",
		".circleci/config.yml", ".circleci/config.yaml",
		"Jenkinsfile", "jenkins.yml",
		".gitlab-ci.yml", ".gitlab-ci.yaml",
		"bitbucket-pipelines.yml",
		"azure-pipelines.yml",
		".drone.yml", ".drone.yaml",
		".woodpecker.yml",
		"cloudbuild.yaml", "cloudbuild.yml",
		".github/workflows/deploy.yml",
		".github/workflows/release.yml",
		".github/workflows/ci.yml",
		".github/workflows/build.yml",
		".github/workflows/main.yml",
		".env.ci", ".env.pipeline",
		"deploy.sh", "deploy.env",
	}

	// Token / secrets files developers leave in web roots
	secretFilePaths := []string{
		".netrc",        // FTP / HTTP creds
		".npmrc",        // npm token
		".pypirc",       // PyPI token
		".boto",         // AWS S3 / boto
		".s3cfg",        // s3cmd config
		"composer.auth.json", "auth.json",
		"keyfile.json", "service-account.json", "credentials.json",
		"client_secret.json", "oauth2.json",
		".htpasswd",
		".ftpconfig",
		"sftp-config.json",       // Sublime SFTP plugin
		"sftpConfig.json",
		"wp-config.php",
		"configuration.php",      // Joomla
		"LocalSettings.php",      // MediaWiki
		"settings.php",           // Drupal
	}

	// Framework debug / info pages that leak env vars in their output
	debugPaths := []string{
		"phpinfo.php", "info.php", "php_info.php", "phpinformation.php",
		"test.php", "1.php", "debug.php", "status.php",
		"_profiler/phpinfo",       // Symfony profiler
		"_profiler/open",
		"telescope/requests",      // Laravel Telescope
		"horizon/api/jobs",        // Laravel Horizon
		"debugbar/assets/stylesheets", // Laravel Debugbar
		"server-status", "server-info", // Apache
		"nginx_status",
		"actuator/env",            // Spring Boot — dumps ALL env vars
		"actuator/configprops",
		"actuator/health",
		"actuator/info",
		"actuator/mappings",
		"metrics",
		"env",                     // Some apps expose /env directly
		"config",
		"health",
		"info",
		"rails/info/properties",   // Rails debug
		"__debug__/",              // Django debug toolbar
		"admin/doc/",              // Django admin docs
	}

	// Log files that sometimes capture credentials from startup / errors
	logPaths := []string{
		"storage/logs/laravel.log",
		"storage/logs/laravel-today.log",
		"var/log/symfony.log", "var/log/dev.log", "var/log/prod.log",
		"log/development.log", "log/production.log",
		"logs/app.log", "logs/application.log", "logs/error.log",
		"debug.log", "app.log", "error.log", "system.log",
		"application.log", "server.log",
		"php_error.log", "php-error.log",
	}

	frameworks := []string{
		"app", "apps", "api", "apis", "backend", "backends", "server", "servers", "web", "webapp", "webapps",
		"portal", "portals", "gateway", "gateways", "services", "service", "microservices", "functions", "lambda",
		"worker", "workers", "batch", "jobs", "cron", "scheduler", "frontend", "frontends", "mobile", "desktop",
		"graphql", "graphql-server", "grpc", "admin", "panel", "dashboard", "monitoring", "observability", "analytics",
	}

	environments := []string{"", "prod", "production", "stage", "staging", "preprod", "dev", "development", "integration", "test", "qa", "beta", "alpha"}
	subdirs := []string{"", "config", "configs", "configuration", "configurations", "deploy", "deployment", "deployments", "docker", "docker-compose", "helm", "k8s", "manifests", "infra", "infrastructure", "scripts", "build", "release", "legacy", "archive", "archived", "tmp", "backup", "backups"}

	for _, base := range baseEnvs {
		add(base)
		for _, env := range environments {
			if env == "" {
				continue
			}
			add(env + "/" + base)
			for _, sub := range subdirs {
				if sub == "" {
					continue
				}
				add(sub + "/" + env + "/" + base)
			}
		}
		for _, fw := range frameworks {
			add(fw + "/" + base)
			for _, env := range environments {
				if env != "" {
					add(fw + "/" + env + "/" + base)
				}
				for _, sub := range subdirs {
					if sub == "" {
						continue
					}
					add(fw + "/" + sub + "/" + base)
					if env != "" {
						add(fw + "/" + sub + "/" + env + "/" + base)
					}
				}
			}
		}
	}

	for _, list := range [][]string{
		baseConfigs, gitPaths, cloudPaths, terraPaths, dockerPaths,
		encodedPaths, mailPaths, backupPaths, cicdPaths, secretFilePaths,
		debugPaths, logPaths,
	} {
		add(list...)
	}

	if wordlist, err := loadWordlist(); err == nil {
		add(wordlist...)
	}

	result := make([]string, 0, len(set))
	for path := range set {
		result = append(result, path)
	}
	sort.Strings(result)
	return result
}

func loadWordlist() ([]string, error) {
	scanner := bufio.NewScanner(strings.NewReader(wordlistData))
	paths := make([]string, 0, 256)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		paths = append(paths, line)
	}
	return paths, scanner.Err()
}

func normalizePath(p string) string {
	if !strings.HasPrefix(p, "/") {
		return strings.TrimPrefix(p, "./")
	}
	return strings.TrimPrefix(p, "//")
}
