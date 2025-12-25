/**
 * OpenList2STRM - Web Management Application v1.1.1
 */

// API Configuration
const API_BASE = '/api';

// State Management
const state = {
    currentPage: 'dashboard',
    status: null,
    folders: [],
    tasks: [],
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
        const scheduler = status.scheduler || {};
        if (scheduler.running) {
            const activeTasks = scheduler.active_tasks || 0;
            scheduleInfo.innerHTML = `
                <span class="badge badge-success">运行中</span>
                <span>活跃任务: ${activeTasks}</span>
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
                    <p>点击"添加文件夹"开始监控</p>
                </div>
            `;
            return;
        }

        container.innerHTML = state.folders.map(folder => {
            const escapedPath = folder.path.replace(/'/g, "\\'");
            return `
            <div class="folder-item">
                <span class="folder-icon">${folder.enabled !== false ? '📁' : '📂'}</span>
                <div class="folder-info">
                    <div class="folder-path">${folder.path}</div>
                    <div class="folder-meta">
                        <span>📄 ${folder.file_count || 0} 个文件</span>
                        <span>🕐 ${folder.last_scan ? formatDate(folder.last_scan) : '从未扫描'}</span>
                        ${folder.from_config ? '<span class="badge badge-info">配置文件</span>' : '<span class="badge badge-warning">动态添加</span>'}
                        ${folder.enabled === false ? '<span class="badge badge-error">已禁用</span>' : ''}
                    </div>
                </div>
                <div class="folder-actions">
                    <button class="btn btn-primary btn-sm" onclick="scanFolder('${escapedPath}')">
                        扫描
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="browseFolder('${escapedPath}')">
                        浏览
                    </button>
                    ${folder.enabled !== false
                    ? `<button class="btn btn-warning btn-sm" onclick="toggleFolder('${escapedPath}', false)">禁用</button>`
                    : `<button class="btn btn-success btn-sm" onclick="toggleFolder('${escapedPath}', true)">启用</button>`
                }
                    ${!folder.from_config
                    ? `<button class="btn btn-danger btn-sm" onclick="deleteFolder('${escapedPath}')">删除</button>`
                    : ''
                }
                </div>
            </div>
        `}).join('');

    } catch (error) {
        showToast('错误', '无法加载文件夹列表', 'error');
    }
}

function openAddFolderModal() {
    document.getElementById('new-folder-path').value = '';
    document.getElementById('add-folder-modal').classList.add('active');
}

async function addFolder() {
    const path = document.getElementById('new-folder-path').value.trim();

    if (!path) {
        showToast('警告', '请输入文件夹路径', 'warning');
        return;
    }

    // Ensure path starts with /
    const normalizedPath = path.startsWith('/') ? path : '/' + path;

    try {
        await apiRequest('/folders', 'POST', {
            path: normalizedPath,
            enabled: true,
        });
        showToast('成功', '文件夹已添加', 'success');
        closeModal('add-folder-modal');
        await loadFolders();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function toggleFolder(path, enabled) {
    try {
        await apiRequest(`/folders/${encodeURIComponent(path.replace(/^\//, ''))}`, 'PUT', {
            enabled: enabled,
        });
        showToast('成功', enabled ? '文件夹已启用' : '文件夹已禁用', 'success');
        await loadFolders();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function deleteFolder(path) {
    if (!confirm(`确定要删除文件夹 "${path}" 吗？`)) return;

    try {
        await apiRequest(`/folders/${encodeURIComponent(path.replace(/^\//, ''))}`, 'DELETE');
        showToast('成功', '文件夹已删除', 'success');
        await loadFolders();
    } catch (error) {
        showToast('错误', error.message, 'error');
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

// ==================== Tasks (v1.1.0 Multi-Task) ====================

async function loadTasks() {
    try {
        // Load tasks from new API
        const result = await apiRequest('/tasks');
        state.tasks = result.tasks || [];

        const container = document.getElementById('tasks-list');

        if (state.tasks.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⏰</div>
                    <div class="empty-state-title">暂无定时任务</div>
                    <p>点击"创建任务"添加新的定时任务</p>
                </div>
            `;
        } else {
            container.innerHTML = state.tasks.map(task => `
                <div class="task-item">
                    <div class="task-item-header">
                        <span class="task-item-name">${task.name || 'Unnamed Task'}</span>
                        <div>
                            ${task.enabled
                    ? (task.paused
                        ? '<span class="badge badge-warning">已暂停</span>'
                        : '<span class="badge badge-success">运行中</span>')
                    : '<span class="badge badge-error">已停用</span>'}
                            ${task.one_time ? '<span class="badge badge-info">一次性</span>' : ''}
                        </div>
                    </div>
                    <div class="task-item-info">
                        <span>📁 ${task.folder || '所有文件夹'}</span>
                        <span>⏰ ${task.cron}</span>
                        <span>🕐 上次: ${task.last_run ? formatDate(task.last_run) : '从未'}</span>
                        <span>📅 下次: ${task.next_run ? formatDate(task.next_run) : '-'}</span>
                    </div>
                    <div class="task-item-actions">
                        <button class="btn btn-primary btn-sm" onclick="runTaskNow('${task.id}')">▶️ 立即执行</button>
                        <button class="btn btn-secondary btn-sm" onclick="openEditTaskModal('${task.id}')">✏️ 编辑</button>
                        ${task.enabled
                    ? (task.paused
                        ? `<button class="btn btn-success btn-sm" onclick="resumeTask('${task.id}')">▶️ 恢复</button>`
                        : `<button class="btn btn-warning btn-sm" onclick="pauseTask('${task.id}')">⏸️ 暂停</button>`)
                    : `<button class="btn btn-success btn-sm" onclick="enableTask('${task.id}')">✅ 启用</button>`}
                        ${task.enabled
                    ? `<button class="btn btn-secondary btn-sm" onclick="disableTask('${task.id}')">❌ 停用</button>`
                    : ''}
                        <button class="btn btn-danger btn-sm" onclick="deleteTask('${task.id}')">🗑️ 删除</button>
                    </div>
                </div>
            `).join('');
        }

        // Load scan history
        try {
            const historyResult = await apiRequest('/scan/history');
            state.history = historyResult.history || [];

            const historyContainer = document.getElementById('scan-history');

            if (state.history.length === 0) {
                historyContainer.innerHTML = '<p class="empty-state">暂无扫描历史</p>';
            } else {
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
            }
        } catch (e) {
            console.log('No scan history available');
        }

    } catch (error) {
        showToast('错误', '无法加载任务信息', 'error');
        document.getElementById('tasks-list').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">❌</div>
                <div class="empty-state-title">加载失败</div>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function openCreateTaskModal() {
    document.getElementById('new-task-name').value = '';
    document.getElementById('new-task-folder').value = '';
    document.getElementById('new-task-cron').value = '0 2 * * *';
    document.getElementById('new-task-one-time').checked = false;
    document.getElementById('create-task-modal').classList.add('active');
}

async function createTask() {
    const name = document.getElementById('new-task-name').value.trim();
    const folder = document.getElementById('new-task-folder').value.trim();
    const cron = document.getElementById('new-task-cron').value.trim();
    const oneTime = document.getElementById('new-task-one-time').checked;

    if (!name) {
        showToast('警告', '请输入任务名称', 'warning');
        return;
    }

    if (!cron) {
        showToast('警告', '请输入 Cron 表达式', 'warning');
        return;
    }

    try {
        await apiRequest('/tasks', 'POST', {
            name,
            folder,
            cron,
            enabled: true,
            one_time: oneTime,
        });
        showToast('成功', '任务已创建', 'success');
        closeModal('create-task-modal');
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

function openEditTaskModal(taskId) {
    const task = state.tasks.find(t => t.id === taskId);
    if (!task) return;

    document.getElementById('edit-task-id').value = taskId;
    document.getElementById('edit-task-name').value = task.name || '';
    document.getElementById('edit-task-folder').value = task.folder || '';
    document.getElementById('edit-task-cron').value = task.cron || '';
    document.getElementById('edit-task-one-time').checked = task.one_time || false;
    document.getElementById('edit-task-modal').classList.add('active');
}

async function updateTask() {
    const taskId = document.getElementById('edit-task-id').value;
    const name = document.getElementById('edit-task-name').value.trim();
    const folder = document.getElementById('edit-task-folder').value.trim();
    const cron = document.getElementById('edit-task-cron').value.trim();
    const oneTime = document.getElementById('edit-task-one-time').checked;

    try {
        await apiRequest(`/tasks/${taskId}`, 'PUT', {
            name,
            folder,
            cron,
            one_time: oneTime,
        });
        showToast('成功', '任务已更新', 'success');
        closeModal('edit-task-modal');
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function deleteTask(taskId) {
    if (!confirm('确定要删除此任务吗？')) return;

    try {
        await apiRequest(`/tasks/${taskId}`, 'DELETE');
        showToast('成功', '任务已删除', 'success');
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function enableTask(taskId) {
    try {
        await apiRequest(`/tasks/${taskId}/enable`, 'POST');
        showToast('成功', '任务已启用', 'success');
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function disableTask(taskId) {
    try {
        await apiRequest(`/tasks/${taskId}/disable`, 'POST');
        showToast('成功', '任务已停用', 'success');
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function pauseTask(taskId) {
    try {
        await apiRequest(`/tasks/${taskId}/pause`, 'POST');
        showToast('成功', '任务已暂停', 'success');
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function resumeTask(taskId) {
    try {
        await apiRequest(`/tasks/${taskId}/resume`, 'POST');
        showToast('成功', '任务已恢复', 'success');
        await loadTasks();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function runTaskNow(taskId) {
    try {
        await apiRequest(`/tasks/${taskId}/run`, 'POST');
        showToast('成功', '任务执行已开始', 'success');
        await loadDashboard();
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

        // Enhanced QoS settings (v1.1.0)
        if (document.getElementById('qos-threading-mode')) {
            document.getElementById('qos-threading-mode').value = settings.qos?.threading_mode || 'multi';
        }
        if (document.getElementById('qos-thread-pool')) {
            document.getElementById('qos-thread-pool').value = settings.qos?.thread_pool_size || 4;
        }

        // STRM settings
        if (document.getElementById('strm-mode')) {
            document.getElementById('strm-mode').value = settings.strm?.mode || 'path';
        }
        if (document.getElementById('strm-url-encode')) {
            document.getElementById('strm-url-encode').checked = settings.strm?.url_encode !== false;
        }
        if (document.getElementById('strm-output-path')) {
            document.getElementById('strm-output-path').value = settings.strm?.output_path || '/strm';
        }

        // Scan settings
        if (document.getElementById('scan-mode')) {
            document.getElementById('scan-mode').value = settings.scan?.mode || 'incremental';
        }
        if (document.getElementById('scan-data-source')) {
            document.getElementById('scan-data-source').value = settings.scan?.data_source || 'cache';
        }

        // Telegram settings
        if (document.getElementById('tg-enabled')) {
            document.getElementById('tg-enabled').checked = settings.telegram?.enabled || false;
        }
        if (document.getElementById('tg-chat-id')) {
            document.getElementById('tg-chat-id').value = settings.telegram?.chat_id || '';
        }

        // Emby settings
        if (document.getElementById('emby-enabled')) {
            document.getElementById('emby-enabled').checked = settings.emby?.enabled || false;
        }
        if (document.getElementById('emby-host')) {
            document.getElementById('emby-host').value = settings.emby?.host || '';
        }
        if (document.getElementById('emby-library-id')) {
            document.getElementById('emby-library-id').value = settings.emby?.library_id || '';
        }

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

async function saveStrmSettings() {
    const mode = document.getElementById('strm-mode').value;
    const urlEncode = document.getElementById('strm-url-encode').checked;
    const outputPath = document.getElementById('strm-output-path').value;

    try {
        await apiRequest('/settings/strm', 'PUT', {
            mode,
            url_encode: urlEncode,
            output_path: outputPath,
        });
        showToast('成功', 'STRM 设置已保存', 'success');
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function saveScanSettings() {
    const mode = document.getElementById('scan-mode').value;
    const dataSource = document.getElementById('scan-data-source').value;

    try {
        await apiRequest('/settings/scan', 'PUT', {
            mode,
            data_source: dataSource,
        });
        showToast('成功', '扫描设置已保存', 'success');
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function saveTelegramSettings() {
    const enabled = document.getElementById('tg-enabled').checked;
    const token = document.getElementById('tg-token').value;
    const chatId = document.getElementById('tg-chat-id').value;

    try {
        await apiRequest('/settings/telegram', 'PUT', {
            enabled,
            token: token || undefined,
            chat_id: chatId || undefined,
        });
        showToast('成功', 'Telegram 设置已保存', 'success');
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function saveEmbySettings() {
    const enabled = document.getElementById('emby-enabled').checked;
    const host = document.getElementById('emby-host').value;
    const apiKey = document.getElementById('emby-api-key').value;
    const libraryId = document.getElementById('emby-library-id').value;

    try {
        await apiRequest('/settings/emby', 'PUT', {
            enabled,
            host: host || undefined,
            api_key: apiKey || undefined,
            library_id: libraryId || undefined,
            notify_on_scan: true,
        });
        showToast('成功', 'Emby 设置已保存', 'success');
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function testEmbyConnection() {
    try {
        showToast('测试中', '正在连接 Emby...', 'info');
        const result = await apiRequest('/settings/emby/test', 'POST');
        if (result.success) {
            showToast('连接成功', `服务器: ${result.server_name} (v${result.version})`, 'success');
        } else {
            showToast('连接失败', result.error, 'error');
        }
    } catch (error) {
        showToast('连接失败', error.message, 'error');
    }
}

async function previewCleanup() {
    try {
        showToast('扫描中', '正在检测待清理项...', 'info');
        const result = await apiRequest('/cleanup/preview', 'POST');

        document.getElementById('cleanup-stats').innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--spacing-sm);">
                <div style="text-align: center; padding: var(--spacing-sm); background: var(--bg-tertiary); border-radius: var(--radius-sm);">
                    <div style="font-size: 1.5rem; font-weight: 600;">${result.broken_symlinks?.length || 0}</div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">无效软链接</div>
                </div>
                <div style="text-align: center; padding: var(--spacing-sm); background: var(--bg-tertiary); border-radius: var(--radius-sm);">
                    <div style="font-size: 1.5rem; font-weight: 600;">${result.empty_dirs?.length || 0}</div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">空目录</div>
                </div>
                <div style="text-align: center; padding: var(--spacing-sm); background: var(--bg-tertiary); border-radius: var(--radius-sm);">
                    <div style="font-size: 1.5rem; font-weight: 600;">${result.total_issues || 0}</div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">总计</div>
                </div>
            </div>
        `;

        showToast('扫描完成', `发现 ${result.total_issues || 0} 个待清理项`, 'info');
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function runCleanup() {
    if (!confirm('确定要执行清理吗？这将删除无效软链接和空目录。')) {
        return;
    }

    try {
        const result = await apiRequest('/cleanup', 'POST', { dry_run: false });
        showToast('清理完成', `已删除 ${result.deleted_count || 0} 项`, 'success');
        await previewCleanup();
    } catch (error) {
        showToast('错误', error.message, 'error');
    }
}

async function testOpenListConnection() {
    const statusDiv = document.getElementById('connection-status');
    try {
        statusDiv.innerHTML = `<div class="badge badge-info">📂 正在测试 OpenList 连接...</div>`;
        const result = await apiRequest('/settings/openlist/test');
        statusDiv.innerHTML = `
            <div class="badge badge-success">✅ OpenList 连接成功</div>
            <div style="margin-top: 8px; font-size: 0.875rem; color: var(--text-secondary);">
                Provider: ${result.provider || 'N/A'} | 根目录项目数: ${result.items || 0}
            </div>
        `;
        showToast('连接成功', 'OpenList 连接正常', 'success');
    } catch (error) {
        statusDiv.innerHTML = `<div class="badge badge-error">❌ OpenList 连接失败: ${error.message}</div>`;
        showToast('连接失败', error.message, 'error');
    }
}

async function testTelegramConnection() {
    const statusDiv = document.getElementById('connection-status');
    try {
        statusDiv.innerHTML = `<div class="badge badge-info">🤖 正在测试 Telegram 机器人...</div>`;
        const result = await apiRequest('/settings/telegram/test', 'POST');
        if (result.success) {
            statusDiv.innerHTML = `
                <div class="badge badge-success">✅ Telegram 机器人连接成功</div>
                <div style="margin-top: 8px; font-size: 0.875rem; color: var(--text-secondary);">
                    机器人名称: @${result.bot_username || 'unknown'}
                </div>
            `;
            showToast('连接成功', `机器人 @${result.bot_username} 工作正常`, 'success');
        } else {
            statusDiv.innerHTML = `<div class="badge badge-error">❌ Telegram 连接失败: ${result.error}</div>`;
            showToast('连接失败', result.error, 'error');
        }
    } catch (error) {
        statusDiv.innerHTML = `<div class="badge badge-error">❌ Telegram 连接失败: ${error.message}</div>`;
        showToast('连接失败', error.message, 'error');
    }
}

// Legacy alias for testConnection
async function testConnection() {
    await testOpenListConnection();
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
