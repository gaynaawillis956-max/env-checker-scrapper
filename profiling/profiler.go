package profiling

import (
	"log"
	"os"
	"runtime/pprof"
)

// Manager controls optional CPU and memory profiling.
type Manager struct {
	enabled bool
	cpuFile *os.File
}

// NewManager constructs a profiling manager.
func NewManager(enabled bool) *Manager {
	return &Manager{enabled: enabled}
}

// Start begins profiling if enabled.
func (m *Manager) Start() {
	if !m.enabled {
		return
	}
	file, err := os.Create("cpu.prof")
	if err != nil {
		log.Printf("unable to create cpu.prof: %v", err)
		return
	}
	m.cpuFile = file
	if err := pprof.StartCPUProfile(file); err != nil {
		log.Printf("unable to start CPU profile: %v", err)
		_ = file.Close()
		m.cpuFile = nil
	}
}

// Stop flushes profiling data and writes a heap profile.
func (m *Manager) Stop() {
	if !m.enabled {
		return
	}
	if m.cpuFile != nil {
		pprof.StopCPUProfile()
		_ = m.cpuFile.Close()
	}
	file, err := os.Create("mem.prof")
	if err != nil {
		log.Printf("unable to create mem.prof: %v", err)
		return
	}
	defer file.Close()
	if err := pprof.WriteHeapProfile(file); err != nil {
		log.Printf("unable to write heap profile: %v", err)
	}
}
