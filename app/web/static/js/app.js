/**
 * OpenList2STRM - Web Management Application
 */

// API Configuration
const API_BASE = '/api';

// State Management
const state = {
    currentPage: 'dashboard',
    status: null,
    folders: [],
    history: [],
    isScanning: false,
    refreshInterval: null,
};

// ==================== Utility Functions ====================

async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);

        // Handle 401 Unauthorized - redirect to login
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Request failed');
        }

        return result;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Logout function
async function logout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, { method: 'POST' });
    } catch (e) {
        // Ignore errors
    }
    window.location.href = '/login';
}

function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
}

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function formatDuration(seconds) {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
}

// ==================== Toast Notifications ====================

function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');

    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ',
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;

    container.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// ==================== Navigation ====================

function navigateTo(page) {
    state.currentPage = page;

    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    // Show correct page
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('hidden', p.id !== `page-${page}`);
    });

    // Close mobile menu
    document.querySelector('.sidebar').classList.remove('open');
    document.querySelector('.sidebar-overlay').classList.remove('active');

    // Load page data
    loadPageData(page);
}

async function loadPageData(page) {
    switch (page) {
        case 'dashboard':
            await loadDashboard();
            break;
        case 'folders':
            await loadFolders();
            break;
        case 'tasks':
            await loadTasks();
            break;
        case 'settings':
            await loadSettings();
            break;
    }
}

// ==================== Dashboard ====================

async function loadDashboard() {
    try {
        const status = await apiRequest('/status');
        state.status = status;

        // Update stats
        document.getElementById('stat-files').textContent = status.cache?.total_files || 0;
        document.getElementById('stat-strm').textContent = status.cache?.total_strm || 0;
        document.getElementById('stat-size').textContent = status.cache?.total_size_human || '0 B';

        // Update last scan
        const lastScan = status.last_scan;
        if (lastScan) {
            document.getElementById('stat-last-scan').textContent = formatDate(lastScan.end_time);
        } else {
            document.getElementById('stat-last-scan').textContent = '从未扫描';
        }

        // Update scheduler status
        const scheduleInfo = document.getElementById('schedule-info');
        if (status.scheduler?.running) {
            scheduleInfo.innerHTML = `
                <span class="badge badge-success">运行中</span>
                <span>下次执行: ${formatDate(status.scheduler.next_run)}</span>
            `;
        } else {
            scheduleInfo.innerHTML = `<span class="badge badge-warning">已暂停</span>`;
        }

        // Update scanner status
        updateScannerStatus(status.scanner);

    } catch (error) {
        showToast('错误', '无法加载状态信息', 'error');
    }
}

function updateScannerStatus(scanner) {
    const container = document.getElementById('scanner-status');

    if (scanner?.running) {
        state.isScanning = true;
        const progress = scanner.progress;
        container.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <span class="card-title">
                        <span class="spinner"></span>
                        扫描进行中
                    </span>
                    <button class="btn btn-danger btn-sm" onclick="cancelScan()">取消</button>
                </div>
                <div style="margin-bottom: var(--spacing-md);">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                        <span>当前路径:</span>
                        <span style="font-family: var(--font-mono); font-size: 0.875rem;">${progress.current_path || '...'}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-bar-fill pulse" style="width: 100%;"></div>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--spacing-sm); text-align: center;">
                    <div>
                        <div style="font-size: 1.25rem; font-weight: 600;">${progress.files_scanned}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">已扫描</div>
                    </div>
                    <div>
                        <div style="font-size: 1.25rem; font-weight: 600; color: var(--success);">${progress.files_created}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">新建</div>
                    </div>
                    <div>
                        <div style="font-size: 1.25rem; font-weight: 600; color: var(--info);">${progress.files_updated}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">更新</div>
                    </div>
                    <div>
                        <div style="font-size: 1.25rem; font-weight: 600; color: var(--warning);">${progress.files_deleted}</div>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">删除</div>
                    </div>
                </div>
            </div>
        `;

        // Start auto-refresh
        if (!state.refreshInterval) {
            state.refreshInterval = setInterval(() => loadDashboard(), 2000);
        }
    } else {
        state.isScanning = false;
        container.innerHTML = '';

        // Stop auto-refresh
        if (state.refreshInterval) {
            clearInterval(state.refreshInterval);
            state.refreshInterval = null;
        }
    }
}

async function triggerScan(folders = null, force = false) {
    if (state.isScanning) {
        showToast('提示', '扫描正在进行中', 'warning');
        return;
    }

    try {
        showToast('开始扫描', '正在启动扫描任务...', 'info');

        const result = await apiRequest('/scan', 'POST', {
            folders: folders,
            force: force,
        });

        showToast('扫描完成',
            `新建: ${result.result.total_files_created}, 更新: ${result.result.total_files_updated}`,
            'success'
        );

        await loadDashboard();

    } catch (error) {
        showToast('扫描失败', error.message, 'error');
    }
}

async function cancelScan() {
    try {
        await apiRequest('/scan/cancel', 'POST');
        showToast('已取消', '扫描任务已取消', 'info');
        await loadDashboard();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

// ==================== Folders ====================

async function loadFolders() {
    try {
        const result = await apiRequest('/folders');
        state.folders = result.folders || [];

        const container = document.getElementById('folders-list');

        if (state.folders.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📁</div>
                    <div class="empty-state-title">暂无监控文件夹</div>
                    <p>请在配置文件中添加要监控的文件夹路径</p>
                </div>
            `;
            return;
        }

        container.innerHTML = state.folders.map(folder => `
            <div class="folder-item">
                <span class="folder-icon">📁</span>
                <div class="folder-info">
                    <div class="folder-path">${folder.path}</div>
                    <div class="folder-meta">
                        <span>📄 ${folder.file_count || 0} 个文件</span>
                        <span>🕐 ${folder.last_scan ? formatDate(folder.last_scan) : '从未扫描'}</span>
                    </div>
                </div>
                <div class="folder-actions">
                    <button class="btn btn-primary btn-sm" onclick="scanFolder('${folder.path}')">
                        扫描
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="browseFolder('${folder.path}')">
                        浏览
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        showToast('错误', '无法加载文件夹列表', 'error');
    }
}

async function scanFolder(path) {
    await triggerScan([path]);
}

async function browseFolder(path) {
    try {
        const result = await apiRequest(`/folders/browse?path=${encodeURIComponent(path)}`);

        // Show browse modal
        const modal = document.getElementById('browse-modal');
        const content = document.getElementById('browse-content');

        content.innerHTML = `
            <div style="margin-bottom: var(--spacing-md);">
                <strong>路径:</strong> <code>${path}</code>
            </div>
            <div style="margin-bottom: var(--spacing-sm);">
                📁 ${result.total_dirs} 个文件夹, 📄 ${result.total_files} 个文件
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>名称</th>
                            <th>类型</th>
                            <th>大小</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${result.directories.map(d => `
                            <tr style="cursor: pointer;" onclick="browseFolder('${path}/${d.name}')">
                                <td>📁 ${d.name}</td>
                                <td>文件夹</td>
                                <td>-</td>
                            </tr>
                        `).join('')}
                        ${result.files.slice(0, 50).map(f => `
                            <tr>
                                <td>📄 ${f.name}</td>
                                <td>文件</td>
                                <td>${formatBytes(f.size)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        modal.classList.add('active');

    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

// ==================== Tasks ====================

async function loadTasks() {
    try {
        // Load schedule
        const schedule = await apiRequest('/tasks/schedule');

        document.getElementById('schedule-cron').value = schedule.cron || '';
        document.getElementById('schedule-status').innerHTML = schedule.running
            ? '<span class="badge badge-success">运行中</span>'
            : '<span class="badge badge-warning">已暂停</span>';

        if (schedule.next_run) {
            document.getElementById('schedule-next').textContent = formatDate(schedule.next_run);
        }

        // Load history
        const historyResult = await apiRequest('/scan/history');
        state.history = historyResult.history || [];

        const historyContainer = document.getElementById('scan-history');

        if (state.history.length === 0) {
            historyContainer.innerHTML = '<p class="empty-state">暂无扫描历史</p>';
            return;
        }

        historyContainer.innerHTML = `
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>文件夹</th>
                            <th>状态</th>
                            <th>扫描</th>
                            <th>新建</th>
                            <th>更新</th>
                            <th>时间</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${state.history.map(h => `
                            <tr>
                                <td style="font-family: var(--font-mono); font-size: 0.75rem;">${h.folder}</td>
                                <td>
                                    <span class="badge badge-${h.status === 'completed' ? 'success' : 'error'}">
                                        ${h.status}
                                    </span>
                                </td>
                                <td>${h.files_scanned}</td>
                                <td style="color: var(--success);">${h.files_created}</td>
                                <td style="color: var(--info);">${h.files_updated}</td>
                                <td>${formatDate(h.end_time)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

    } catch (error) {
        showToast('错误', '无法加载任务信息', 'error');
    }
}

async function updateSchedule() {
    const cron = document.getElementById('schedule-cron').value;

    try {
        await apiRequest('/tasks/schedule', 'PUT', { cron });
        showToast('成功', '定时任务已更新', 'success');
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function toggleScheduler(pause) {
    try {
        if (pause) {
            await apiRequest('/tasks/schedule/pause', 'POST');
            showToast('已暂停', '定时任务已暂停', 'info');
        } else {
            await apiRequest('/tasks/schedule/resume', 'POST');
            showToast('已恢复', '定时任务已恢复', 'success');
        }
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

// ==================== Settings ====================

async function loadSettings() {
    try {
        const settings = await apiRequest('/settings');

        // QoS settings
        document.getElementById('qos-qps').value = settings.qos?.qps || 5;
        document.getElementById('qos-concurrent').value = settings.qos?.max_concurrent || 3;
        document.getElementById('qos-interval').value = settings.qos?.interval || 200;

        // Display other settings
        document.getElementById('settings-display').innerHTML = `
            <div class="form-group">
                <label class="form-label">OpenList 地址</label>
                <input type="text" class="form-input" value="${settings.openlist?.host || ''}" readonly>
            </div>
            <div class="form-group">
                <label class="form-label">输出路径</label>
                <input type="text" class="form-input" value="${settings.paths?.output || '/strm'}" readonly>
            </div>
            <div class="form-group">
                <label class="form-label">增量更新</label>
                <input type="text" class="form-input" 
                    value="${settings.incremental?.enabled ? '启用' : '禁用'} (${settings.incremental?.check_method})" 
                    readonly>
            </div>
            <div class="form-group">
                <label class="form-label">Telegram 机器人</label>
                <input type="text" class="form-input" 
                    value="${settings.telegram?.enabled ? '已启用' : '未启用'}" 
                    readonly>
            </div>
        `;

    } catch (error) {
        showToast('错误', '无法加载设置', 'error');
    }
}

async function updateQoS() {
    const qps = parseFloat(document.getElementById('qos-qps').value);
    const maxConcurrent = parseInt(document.getElementById('qos-concurrent').value);
    const interval = parseInt(document.getElementById('qos-interval').value);

    try {
        await apiRequest('/settings/qos', 'PUT', {
            qps,
            max_concurrent: maxConcurrent,
            interval,
        });
        showToast('成功', 'QoS 设置已更新', 'success');
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function testConnection() {
    try {
        const result = await apiRequest('/settings/openlist/test');
        showToast('连接成功', `Provider: ${result.provider}, Items: ${result.items}`, 'success');
    } catch (error) {
        showToast('连接失败', error.message, 'error');
    }
}

async function clearCache() {
    if (!confirm('确定要清除所有缓存数据吗？这将删除所有扫描历史记录。')) {
        return;
    }

    try {
        await apiRequest('/settings/cache/clear', 'POST');
        showToast('成功', '缓存已清除', 'success');
        await loadDashboard();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function reloadConfig() {
    try {
        await apiRequest('/settings/reload', 'POST');
        showToast('成功', '配置已重新加载', 'success');
        await loadSettings();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

// ==================== Config Backup/Restore ====================

async function exportConfig() {
    try {
        const response = await fetch(`${API_BASE}/settings/export`);
        const blob = await response.blob();

        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `openlist2strm_config_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('成功', '配置已导出', 'success');
    } catch (error) {
        showToast('错误', '导出失败: ' + error.message, 'error');
    }
}

async function importConfig(input) {
    const file = input.files[0];
    if (!file) return;

    if (!confirm('确定要导入此配置文件吗？现有配置将被合并（密码和Token不会被覆盖）。')) {
        input.value = '';
        return;
    }

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/settings/import`, {
            method: 'POST',
            body: formData,
        });

        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Import failed');
        }

        showToast('成功', '配置已导入', 'success');
        await loadSettings();
    } catch (error) {
        showToast('错误', '导入失败: ' + error.message, 'error');
    } finally {
        input.value = '';
    }
}

// ==================== OpenList Token ====================

function toggleTokenVisibility() {
    const input = document.getElementById('openlist-token');
    input.type = input.type === 'password' ? 'text' : 'password';
}

async function saveOpenListToken() {
    const token = document.getElementById('openlist-token').value.trim();

    if (!token) {
        showToast('警告', '请输入 Token', 'warning');
        return;
    }

    try {
        await apiRequest('/settings/openlist/token', 'PUT', { token });
        showToast('成功', 'OpenList Token 已保存', 'success');
        document.getElementById('openlist-token').value = '';
        await testConnection();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

// ==================== Mobile Menu ====================

function toggleMobileMenu() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');

    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
}

// ==================== Initialization ====================

document.addEventListener('DOMContentLoaded', () => {
    // Setup navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            navigateTo(item.dataset.page);
        });
    });

    // Setup mobile menu
    document.querySelector('.mobile-menu-toggle').addEventListener('click', toggleMobileMenu);
    document.querySelector('.sidebar-overlay').addEventListener('click', toggleMobileMenu);

    // Initial load
    navigateTo('dashboard');

    // Periodic refresh for dashboard
    setInterval(() => {
        if (state.currentPage === 'dashboard' && !state.isScanning) {
            loadDashboard();
        }
    }, 30000); // Refresh every 30 seconds
});
