import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import axios from 'axios';
import './CrawlerMain.css';

// API 配置
const API_BASE_URL = '/api/crawl';
const SOCKET_URL = 'http://localhost:5000/crawl';

// 任务状态常量
const TASK_STATUS = {
    PENDING: 'PENDING',
    RUNNING: 'RUNNING',
    PAUSED: 'PAUSED',
    COMPLETED: 'COMPLETED',
    FAILED: 'FAILED',
    STOPPED: 'STOPPED'
};

// 组件：日志查看器
const LogViewer = ({ taskId, logs }) => {
    const logContainerRef = useRef(null);
    const logEndRef = useRef(null);
    const [isPinnedToBottom, setIsPinnedToBottom] = useState(false);

    const updatePinnedState = () => {
        const el = logContainerRef.current;
        if (!el) return;
        const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        setIsPinnedToBottom(distanceToBottom <= 40);
    };

    useEffect(() => {
        if (!isPinnedToBottom) return;
        const el = logContainerRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    }, [logs, isPinnedToBottom]);

    return (
        <div className="log-viewer glass-panel">
            <div className="panel-header">
                <h3><i className="fas fa-terminal"></i> 实时日志</h3>
                <span className="log-count">{logs.length} 条</span>
            </div>
            <div
                className="log-content custom-scrollbar"
                ref={logContainerRef}
                onScroll={updatePinnedState}
            >
                {logs.length === 0 ? <p className="no-data">等待日志...</p> : logs.map((log, index) => (
                    <div key={index} className={`log-entry ${log.level?.toLowerCase()} ${log.category}`}>
                        <span className="log-time">{log.timestamp}</span>
                        <span className="log-level">[{log.level}]</span>
                        <span className="log-category">[{log.category || 'general'}]</span>
                        <span className="log-message">{log.message}</span>
                        {log.extra && Object.keys(log.extra).length > 0 && (
                            <span className="log-extra">{JSON.stringify(log.extra)}</span>
                        )}
                    </div>
                ))}
                <div ref={logEndRef} />
            </div>
        </div>
    );
};

// 组件：结果查看器
const ResultViewer = ({ taskId, results }) => {
    const tableContainerRef = useRef(null);
    const resultEndRef = useRef(null);
    const [isPinnedToBottom, setIsPinnedToBottom] = useState(false);

    const updatePinnedState = () => {
        const el = tableContainerRef.current;
        if (!el) return;
        const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        setIsPinnedToBottom(distanceToBottom <= 40);
    };

    useEffect(() => {
        if (!isPinnedToBottom) return;
        const el = tableContainerRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    }, [results, isPinnedToBottom]);

    const handleExport = async () => {
        if (!taskId) return;
        try {
            const response = await axios.get(`${API_BASE_URL}/export/${taskId}`, {
                responseType: 'blob',
            });
            
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `crawl_results_${taskId}.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Export error:", err);
            alert("导出失败，请稍后重试。");
        }
    };

    if (!results || results.length === 0) return (
        <div className="result-viewer glass-panel">
            <div className="panel-header">
                <h3><i className="fas fa-table"></i> 结果</h3>
            </div>
            <p className="no-data">暂无结果。</p>
        </div>
    );

    return (
        <div className="result-viewer glass-panel">
            <div className="panel-header">
                <h3><i className="fas fa-table"></i> 结果 ({results.length})</h3>
                <button className="action-btn primary small" onClick={handleExport} title="导出 Excel">
                    <i className="fas fa-download"></i> 导出
                </button>
            </div>
            <div
                className="table-container custom-scrollbar"
                ref={tableContainerRef}
                onScroll={updatePinnedState}
            >
                <table>
                    <thead>
                        <tr>
                            <th>标题</th>
                            <th>深度</th>
                            <th>作者</th>
                            <th>URL</th>
                            <th>摘要</th>
                            <th>关键词</th>
                            <th>时间</th>
                            <th>PDF数量</th>
                        </tr>
                    </thead>
                    <tbody>
                        {results.map((res, idx) => (
                            <tr key={idx} className={res.tags && res.tags.includes('big_site') ? 'highlight-row' : ''}>
                                <td title={res.title}>
                                    {res.tags && res.tags.includes('big_site') && <span title="大站优先" style={{marginRight: '5px'}}>⭐</span>}
                                    {res.title || '-'}
                                </td>
                                <td>{res.depth}</td>
                                <td title={res.author}>{res.author || '-'}</td>
                                <td><a href={res.url} target="_blank" rel="noopener noreferrer" title={res.url}>{res.url}</a></td>
                                <td title={res.abstract} className="truncate-cell">{res.abstract || '-'}</td>
                                <td title={res.keywords ? res.keywords.join(', ') : ''}>{res.keywords ? res.keywords.join(', ') : '-'}</td>
                                <td>{new Date(res.crawled_at).toLocaleTimeString()}</td>
                                <td>{res.pdf_count}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                <div ref={resultEndRef} />
            </div>
        </div>
    );
};

const formatTaskDisplayName = (taskName, taskId) => {
    const name = (taskName || '').trim();
    if (!name) return taskId || '';
    if (taskId && name === taskId) return taskId;

    if (taskId && name.includes(taskId)) {
        const cleaned = name.replaceAll(taskId, '').trim();
        return cleaned || taskId;
    }

    const uuidMatch = name.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    if (!uuidMatch) return name;

    const prefix = name.slice(0, uuidMatch.index).trim();
    if (prefix) return prefix;
    return name;
};

const CrawlerMain = () => {
    // 状态管理
    const [tasks, setTasks] = useState([]);
    const [selectedTaskId, setSelectedTaskId] = useState(null);
    const [runningTaskId, setRunningTaskId] = useState(null);
    const [logs, setLogs] = useState({}); // { taskId: [logs] }
    const [results, setResults] = useState({}); // { taskId: [results] }
    const [taskStatuses, setTaskStatuses] = useState({}); // { taskId: status }
    const [viewMode, setViewMode] = useState('logs'); // 'logs' or 'results'

    // 创建任务表单状态
    const [formData, setFormData] = useState({
        name: '', // Added name
        start_url: 'https://crawler-test.com/',
        strategy: 'BFS',
        max_depth: 3,
        max_pages: 5,
        interval: 0.2,
        allow_domains: '',
        priority_domains: '' // Added priority_domains
    });

    // 暂停时的配置编辑状态
    const [editConfig, setEditConfig] = useState({
        interval: 1.0,
        max_pages: 100,
        max_depth: 3
    });

    const socketRef = useRef(null);
    const mainContentRef = useRef(null);

    // 初始化 WebSocket（只在组件挂载时执行一次）
    useEffect(() => {
        // Load existing tasks
        const loadTasks = async () => {
            try {
                const res = await axios.get(`${API_BASE_URL}/tasks`);
                // Normalize dates
                const loadedTasks = res.data.map(t => ({
                    ...t,
                    createdAt: t.created_at ? new Date(t.created_at) : new Date()
                }));
                setTasks(loadedTasks);
            } catch (err) {
                console.error("Failed to load tasks", err);
            }
        };
        loadTasks();

        socketRef.current = io(SOCKET_URL);

        socketRef.current.on('connect', () => {
            console.log('WebSocket connected');
        });

        socketRef.current.on('crawl_log', (data) => {
            // 业务日志 (room=taskId)
            const { task_id, event_type, data: eventData } = data;
            if (task_id) {
                setLogs(prev => ({
                    ...prev,
                    [task_id]: [...(prev[task_id] || []), data]
                }));

                // Real-time result update
                if (event_type === 'PageCrawledEvent' || event_type === 'PAGE_CRAWLED') {
                    const newResult = {
                        title: eventData.title,
                        url: eventData.url,
                        depth: eventData.depth,
                        crawled_at: data.timestamp,
                        pdf_count: eventData.pdf_count,
                        author: eventData.author,
                        abstract: eventData.abstract,
                        keywords: eventData.keywords,
                        tags: eventData.tags || [] // Added tags
                    };
                    
                    setResults(prev => {
                        const currentResults = prev[task_id] || [];
                        // Check for duplicates based on URL to avoid list growing indefinitely with same items if re-emitted
                        if (currentResults.some(r => r.url === newResult.url)) {
                             return prev;
                        }
                        return {
                            ...prev,
                            [task_id]: [...currentResults, newResult]
                        };
                    });
                }
            }
        });

        socketRef.current.on('tech_log', (data) => {
            if (runningTaskId) {
                setLogs(prev => ({
                    ...prev,
                    [runningTaskId]: [...(prev[runningTaskId] || []), { ...data, category: 'tech_log' }]
                }));
            }
        });

        socketRef.current.on('broadcast', (data) => {
            console.log("Broadcast:", data);
        });

        return () => {
            if (socketRef.current) socketRef.current.disconnect();
        };
    }, []);

    // 监听选中任务变化，自动加入房间，并重置滚动条
    useEffect(() => {
        if (selectedTaskId && socketRef.current) {
            console.log(`Joining room: ${selectedTaskId}`);
            socketRef.current.emit('join', { room: selectedTaskId });
        }
        // Reset scroll position when switching tasks
        if (mainContentRef.current) {
            mainContentRef.current.scrollTop = 0;
        }
    }, [selectedTaskId]);

    // 轮询状态
    useEffect(() => {
        const intervalId = setInterval(async () => {
            if (selectedTaskId) {
                await fetchStatus(selectedTaskId);
            }
            if (runningTaskId) {
                await fetchStatus(runningTaskId);
            }
        }, 2000);

        return () => clearInterval(intervalId);
    }, [selectedTaskId, runningTaskId]);

    // 当选中任务且处于暂停状态时，同步配置到编辑表单
    useEffect(() => {
        if (selectedTaskId && tasks.length > 0) {
            const currentTask = tasks.find(t => t.id === selectedTaskId);
            // 只要切换任务，或者任务状态变为暂停，就尝试更新编辑表单的默认值
            // 这里我们不仅在暂停时更新，选中任务时也更新，以便用户查看当前配置
            if (currentTask && currentTask.config) {
                setEditConfig({
                    interval: currentTask.config.interval || 1.0,
                    max_pages: currentTask.config.max_pages || 100,
                    max_depth: currentTask.config.max_depth || 3
                });
            }
        }
    }, [selectedTaskId, tasks]);

    const fetchStatus = async (taskId) => {
        try {
            const res = await axios.get(`${API_BASE_URL}/status/${taskId}`);
            const statusData = res.data;
            setTaskStatuses(prev => ({ ...prev, [taskId]: statusData }));

            const currentResultCount = results[taskId]?.length || 0;
            if (statusData.result_count > currentResultCount) {
                await fetchResults(taskId);
            }

            // 更新 runningTaskId 状态
            if (statusData.status === TASK_STATUS.RUNNING) {
                setRunningTaskId(taskId);
            } else if (taskId === runningTaskId && statusData.status !== TASK_STATUS.RUNNING) {
                if (statusData.status === TASK_STATUS.PAUSED) {
                    setRunningTaskId(taskId);
                } else {
                    setRunningTaskId(null);
                    fetchResults(taskId);
                }
            }

            if ([TASK_STATUS.COMPLETED, TASK_STATUS.STOPPED, TASK_STATUS.FAILED].includes(statusData.status)) {
                if (!results[taskId]) {
                    fetchResults(taskId);
                }
            }

        } catch (err) {
            console.error("Failed to fetch status", err);
        }
    };

    const fetchResults = async (taskId) => {
        try {
            const res = await axios.get(`${API_BASE_URL}/results/${taskId}`);
            setResults(prev => ({ ...prev, [taskId]: res.data }));
        } catch (err) {
            console.error("Failed to fetch results", err);
        }
    };

    const handleCreateTask = async (e) => {
        e.preventDefault();
        try {
            const payload = {
                ...formData,
                allow_domains: formData.allow_domains.split(',').map(d => d.trim()).filter(d => d),
                priority_domains: formData.priority_domains.split(',').map(d => d.trim()).filter(d => d)
            };

            const res = await axios.post(`${API_BASE_URL}/create`, payload);
            const newTaskId = res.data.task_id;

            const newTask = {
                id: newTaskId,
                name: formData.name || newTaskId, // Store name locally initially
                config: payload,
                createdAt: new Date()
            };

            setTasks([...tasks, newTask]);
            setLogs(prev => ({ ...prev, [newTaskId]: [] }));
            setSelectedTaskId(newTaskId);

            // 重置表单
            setFormData({
                name: '',
                start_url: 'https://crawler-test.com/',
                strategy: 'BFS',
                max_depth: 3,
                max_pages: 5,
                interval: 0.2,
                allow_domains: '',
                priority_domains: ''
            });

            // alert(`Task Created: ${newTaskId}`); // Removed alert for smoother UX
        } catch (err) {
            alert(`失败: ${err.response?.data?.error || err.message}`);
        }
    };

    const handleStart = async (taskId) => {
        if (runningTaskId && runningTaskId !== taskId) {
            alert(`任务 ${runningTaskId} 正在运行,请先停止它。`);
            return;
        }
        try {
            await axios.post(`${API_BASE_URL}/start/${taskId}`);
            setRunningTaskId(taskId);
            if (socketRef.current) {
                socketRef.current.emit('join', { room: taskId });
            }
            await fetchStatus(taskId);
        } catch (err) {
            alert(`启动失败: ${err.response?.data?.error || err.message}`);
        }
    };

    const handlePause = async (taskId) => {
        try {
            await axios.post(`${API_BASE_URL}/pause/${taskId}`);
            await fetchStatus(taskId);
        } catch (err) {
            alert(`暂停失败: ${err.message}`);
        }
    };

    const handleResume = async (taskId) => {
        try {
            await axios.post(`${API_BASE_URL}/resume/${taskId}`);
            await fetchStatus(taskId);
        } catch (err) {
            alert(`继续失败: ${err.message}`);
        }
    };

    const handleStop = async (taskId) => {
        try {
            await axios.post(`${API_BASE_URL}/stop/${taskId}`);
            await fetchStatus(taskId);
        } catch (err) {
            alert(`停止失败: ${err.message}`);
        }
    };

    const handleUpdateConfig = async (taskId) => {
        try {
            await axios.post(`${API_BASE_URL}/config/${taskId}`, editConfig);
            
            // Update local tasks state to reflect changes immediately
            setTasks(prevTasks => prevTasks.map(t => 
                t.id === taskId 
                    ? { ...t, config: { ...t.config, ...editConfig } }
                    : t
            ));

            alert("配置已更新!");
        } catch (err) {
            alert(`更新失败: ${err.message}`);
        }
    };

    // 渲染
    const currentStatus = selectedTaskId ? taskStatuses[selectedTaskId] : null;
    const isPaused = currentStatus?.status === TASK_STATUS.PAUSED;
    const selectedTask = selectedTaskId ? tasks.find(t => t.id === selectedTaskId) : null;
    const currentTaskName = selectedTaskId
        ? formatTaskDisplayName(selectedTask?.name || currentStatus?.name, selectedTaskId)
        : '';

    return (
        <div className="crawler-app">
            <div className="sidebar">
                <div className="sidebar-header">
                    <h2><i className="fas fa-spider"></i> CrawlFlow</h2>
                    <button className="new-task-btn" onClick={() => setSelectedTaskId(null)}>
                        <i className="fas fa-plus"></i> 新建任务
                    </button>
                </div>
                <ul className="task-list custom-scrollbar">
                    {tasks.map(task => {
                        const displayName = formatTaskDisplayName(task.name, task.id);
                        const hasCustomName = Boolean(task.name && task.name !== task.id);
                        return (
                        <li
                            key={task.id}
                            className={`task-item ${selectedTaskId === task.id ? 'active' : ''}`}
                            onClick={() => setSelectedTaskId(task.id)}
                        >
                            <div className="task-info">
                                <span className="task-name" title={task.name || task.id}>
                                    {hasCustomName ? displayName : task.id.substring(0, 8)}
                                </span>
                                {!hasCustomName && <span className="task-id-sub">{task.id.substring(0, 6)}...</span>}
                            </div>
                            <span className={`status-dot ${(taskStatuses[task.id]?.status || 'PENDING').toLowerCase()}`}></span>
                        </li>
                        );
                    })}
                </ul>
            </div>
            <div className="main-content" ref={mainContentRef}>
                {!selectedTaskId ? (
                    <div className="create-task-container glass-panel">
                        <h2>创建新任务</h2>
                        <form onSubmit={handleCreateTask} className="create-form">
                            <div className="form-group full-width">
                                <label>任务名称</label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                                    placeholder="例如:技术博客爬取"
                                />
                            </div>
                            <div className="form-group full-width">
                                <label>起始URL</label>
                                <input
                                    type="text"
                                    value={formData.start_url}
                                    onChange={e => setFormData({ ...formData, start_url: e.target.value })}
                                    required
                                    placeholder="https://example.com"
                                />
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>策略</label>
                                    <select
                                        value={formData.strategy}
                                        onChange={e => setFormData({ ...formData, strategy: e.target.value })}
                                    >
                                        <option value="BFS">BFS (广度优先)</option>
                                        <option value="DFS">DFS (深度优先)</option>
                                        <option value="BIG_SITE_FIRST">大站优先</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>最大深度</label>
                                    <input
                                        type="number"
                                        value={formData.max_depth}
                                        onChange={e => setFormData({ ...formData, max_depth: parseInt(e.target.value) })}
                                    />
                                </div>
                            </div>

                            {formData.strategy === 'BIG_SITE_FIRST' && (
                                <div className="form-group full-width priority-domains-alert">
                                    <label>⭐ 大站域名设置 (逗号分隔)</label>
                                    <input
                                        type="text"
                                        value={formData.priority_domains}
                                        onChange={e => setFormData({ ...formData, priority_domains: e.target.value })}
                                        placeholder="例如: books.toscrape.com, quotes.toscrape.com"
                                    />
                                    <small>
                                        输入的大站域名将获得最高优先级，其下的页面会优先被爬取。
                                    </small>
                                </div>
                            )}

                            <div className="form-row">
                                <div className="form-group">
                                    <label>最大页数</label>
                                    <input
                                        type="number"
                                        value={formData.max_pages}
                                        onChange={e => setFormData({ ...formData, max_pages: parseInt(e.target.value) })}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>间隔 (秒)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={formData.interval}
                                        onChange={e => setFormData({ ...formData, interval: parseFloat(e.target.value) })}
                                    />
                                </div>
                            </div>
                            <div className="form-group full-width">
                                <label>允许的域名 (逗号分隔)</label>
                                <input
                                    type="text"
                                    value={formData.allow_domains}
                                    onChange={e => setFormData({ ...formData, allow_domains: e.target.value })}
                                    placeholder="example.com, google.com"
                                />
                            </div>

                            <button type="submit" className="submit-btn">
                                <i className="fas fa-rocket"></i> 启动爬虫
                            </button>
                        </form>
                    </div>
                ) : (
                    <div className="task-dashboard">
                        <div className="dashboard-header glass-panel">
                            <div className="header-left">
                                <h2>{currentTaskName}</h2>
                            </div>
                            <div className="header-right">
                                <div className="status-indicator">
                                    <span className={`status-badge ${(currentStatus?.status || 'PENDING').toLowerCase()}`}>
                                        {currentStatus?.status || 'PENDING'}
                                    </span>
                                </div>
                                <div className="metrics">
                                    <div className="metric-item">
                                        <span className="label">已访问</span>
                                        <span className="value">{currentStatus?.visited_count || 0}</span>
                                    </div>
                                    <div className="metric-item">
                                        <span className="label">队列</span>
                                        <span className="value">{currentStatus?.queue_size || 0}</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="controls-bar glass-panel">
                            <button className="control-btn start" onClick={() => handleStart(selectedTaskId)} disabled={currentStatus?.status === TASK_STATUS.RUNNING || currentStatus?.status === TASK_STATUS.COMPLETED || currentStatus?.status === TASK_STATUS.PAUSED}>
                                <i className="fas fa-play"></i> 开始
                            </button>
                            <button className="control-btn pause" onClick={() => handlePause(selectedTaskId)} disabled={currentStatus?.status !== TASK_STATUS.RUNNING}>
                                <i className="fas fa-pause"></i> 暂停
                            </button>
                            <button className="control-btn resume" onClick={() => handleResume(selectedTaskId)} disabled={currentStatus?.status !== TASK_STATUS.PAUSED}>
                                <i className="fas fa-forward"></i> 继续
                            </button>
                            <button className="control-btn stop" onClick={() => handleStop(selectedTaskId)} disabled={[TASK_STATUS.STOPPED, TASK_STATUS.COMPLETED, TASK_STATUS.FAILED].includes(currentStatus?.status)}>
                                <i className="fas fa-stop"></i> 停止
                            </button>
                            
                            <div className="view-toggles">
                                <button 
                                    className={`view-btn ${viewMode === 'logs' ? 'active' : ''}`} 
                                    onClick={() => setViewMode('logs')}
                                >
                                    <i className="fas fa-terminal"></i> 日志
                                </button>
                                <button 
                                    className={`view-btn ${viewMode === 'results' ? 'active' : ''}`} 
                                    onClick={() => setViewMode('results')}
                                >
                                    <i className="fas fa-table"></i> 结果
                                </button>
                            </div>
                        </div>

                        {isPaused && (
                            <div className="config-editor glass-panel">
                                <h3><i className="fas fa-cog"></i> 调整配置 (已暂停)</h3>
                                <div className="form-row">
                                    <div className="form-group">
                                        <label>间隔</label>
                                        <input
                                            type="number" step="0.1"
                                            value={editConfig.interval}
                                            onChange={e => setEditConfig({ ...editConfig, interval: parseFloat(e.target.value) })}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>最大页数</label>
                                        <input
                                            type="number"
                                            value={editConfig.max_pages}
                                            onChange={e => setEditConfig({ ...editConfig, max_pages: parseInt(e.target.value) })}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>最大深度</label>
                                        <input
                                            type="number"
                                            value={editConfig.max_depth}
                                            onChange={e => setEditConfig({ ...editConfig, max_depth: parseInt(e.target.value) })}
                                        />
                                    </div>
                                    <button className="update-btn" onClick={() => handleUpdateConfig(selectedTaskId)}>更新</button>
                                </div>
                            </div>
                        )}

                        <div className="dashboard-content-wrapper">
                            {viewMode === 'logs' ? (
                                <LogViewer taskId={selectedTaskId} logs={logs[selectedTaskId] || []} />
                            ) : (
                                <ResultViewer taskId={selectedTaskId} results={results[selectedTaskId]} />
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CrawlerMain;
