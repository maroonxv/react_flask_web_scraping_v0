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
    const logEndRef = useRef(null);

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <div className="log-viewer">
            <h3>实时日志</h3>
            <div className="log-content">
                {logs.length === 0 ? <p>暂无日志...</p> : logs.map((log, index) => (
                    <div key={index} className={`log-entry ${log.level?.toLowerCase()} ${log.category}`}>
                        <span className="log-time">{new Date(log.timestamp).toLocaleTimeString()}</span>
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
const ResultViewer = ({ results }) => {
    if (!results || results.length === 0) return <p>暂无爬取结果。</p>;

    return (
        <div className="result-viewer">
            <h3>爬取结果 ({results.length})</h3>
            <table>
                <thead>
                    <tr>
                        <th>标题</th>
                        <th>URL</th>
                        <th>爬取时间</th>
                        <th>PDF数</th>
                    </tr>
                </thead>
                <tbody>
                    {results.map((res, idx) => (
                        <tr key={idx}>
                            <td>{res.title || '-'}</td>
                            <td><a href={res.url} target="_blank" rel="noopener noreferrer">{res.url}</a></td>
                            <td>{res.crawled_at}</td>
                            <td>{res.pdf_count}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

const CrawlerMain = () => {
    // 状态管理
    const [tasks, setTasks] = useState([]);
    const [selectedTaskId, setSelectedTaskId] = useState(null);
    const [runningTaskId, setRunningTaskId] = useState(null);
    const [logs, setLogs] = useState({}); // { taskId: [logs] }
    const [results, setResults] = useState({}); // { taskId: [results] }
    const [taskStatuses, setTaskStatuses] = useState({}); // { taskId: status }
    
    // 创建任务表单状态
    const [formData, setFormData] = useState({
        start_url: 'https://crawler-test.com/',
        strategy: 'BFS',
        max_depth: 3,
        max_pages: 100,
        interval: 1.0,
        allow_domains: ''
    });

    // 暂停时的配置编辑状态
    const [editConfig, setEditConfig] = useState({
        interval: 1.0,
        max_pages: 100,
        max_depth: 3
    });

    const socketRef = useRef(null);

    // 初始化 WebSocket
    useEffect(() => {
        socketRef.current = io(SOCKET_URL);

        socketRef.current.on('connect', () => {
            console.log('WebSocket connected');
        });

        socketRef.current.on('crawl_log', (data) => {
            // 业务日志 (room=taskId)
            const { task_id } = data;
            if (task_id) {
                setLogs(prev => ({
                    ...prev,
                    [task_id]: [...(prev[task_id] || []), data]
                }));
            }
        });

        socketRef.current.on('tech_log', (data) => {
            // 技术日志 (广播) - 尝试关联到当前选中的任务，或者放到系统日志
            // 这里简单处理：如果当前有选中的任务，且日志似乎相关（或者直接显示在所有任务的日志里？）
            // 由于技术日志可能没有 task_id，我们暂时只在 LogViewer 中显示
            // 为了演示，我们把 tech_log 广播给所有存在的任务日志，或者只给 runningTaskId
            if (runningTaskId) {
                setLogs(prev => ({
                    ...prev,
                    [runningTaskId]: [...(prev[runningTaskId] || []), { ...data, category: 'tech_log' }]
                }));
            }
        });
        
        // 监听广播消息
        socketRef.current.on('broadcast', (data) => {
             console.log("Broadcast:", data);
        });

        return () => {
            if (socketRef.current) socketRef.current.disconnect();
        };
    }, [runningTaskId]);

    // 轮询状态 (简化实现，生产环境应用 WebSocket 推送状态变化)
    useEffect(() => {
        const intervalId = setInterval(async () => {
            if (selectedTaskId) {
                await fetchStatus(selectedTaskId);
            }
            // 检查是否有正在运行的任务
            // 实际上应该遍历所有 active 的任务
            if (runningTaskId) {
                await fetchStatus(runningTaskId);
            }
        }, 2000);

        return () => clearInterval(intervalId);
    }, [selectedTaskId, runningTaskId]);

    const fetchStatus = async (taskId) => {
        try {
            const res = await axios.get(`${API_BASE_URL}/status/${taskId}`);
            const statusData = res.data;
            setTaskStatuses(prev => ({ ...prev, [taskId]: statusData }));
            
            // 更新 runningTaskId 状态
            if (statusData.status === TASK_STATUS.RUNNING) {
                setRunningTaskId(taskId);
            } else if (taskId === runningTaskId && statusData.status !== TASK_STATUS.RUNNING) {
                // 如果之前记录为运行中，现在变了，且是暂停或停止
                if (statusData.status === TASK_STATUS.PAUSED) {
                     // 保持 runningTaskId 锁定，直到完全停止？
                     // 需求：同一时间只能有一个爬取任务在运行。暂停算不算占用运行名额？
                     // 通常暂停意味着资源未释放，但也可能允许其他任务运行。
                     // 这里假设严格限制：暂停也占用，直到 STOPPED/COMPLETED/FAILED
                     setRunningTaskId(taskId);
                } else {
                     setRunningTaskId(null);
                     // 任务结束，获取结果
                     fetchResults(taskId);
                }
            }
            
            // 如果状态是 COMPLETED/STOPPED/FAILED 且还没有结果，获取结果
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
                allow_domains: formData.allow_domains.split(',').map(d => d.trim()).filter(d => d)
            };
            
            const res = await axios.post(`${API_BASE_URL}/create`, payload);
            const newTaskId = res.data.task_id;
            
            const newTask = {
                id: newTaskId,
                config: payload,
                createdAt: new Date()
            };
            
            setTasks([...tasks, newTask]);
            setLogs(prev => ({ ...prev, [newTaskId]: [] }));
            setSelectedTaskId(newTaskId);
            
            // 重置表单
            setFormData({
                start_url: 'https://crawler-test.com/',
                strategy: 'BFS',
                max_depth: 3,
                max_pages: 100,
                interval: 1.0,
                allow_domains: ''
            });
            
            alert(`任务创建成功: ${newTaskId}`);
        } catch (err) {
            alert(`创建失败: ${err.response?.data?.error || err.message}`);
        }
    };

    const handleStart = async (taskId) => {
        if (runningTaskId && runningTaskId !== taskId) {
            alert(`已有任务 ${runningTaskId} 在运行，请先结束它！`);
            return;
        }
        try {
            await axios.post(`${API_BASE_URL}/start/${taskId}`);
            setRunningTaskId(taskId);
            // 加入 WebSocket room
            // 后端实现是直接 emit 到 room=taskId，socket.io 客户端需要 emit 'join' 吗？
            // Flask-SocketIO 的默认行为是 client 即使不 emit join，也收不到指定 room 的消息，除非 server 显式把 sid 加入 room
            // 或者 server 广播。
            // 检查后端代码：`self._socketio.emit(..., room=task_id)`
            // 前端必须加入房间。通常做法是 `socket.emit('join', {room: taskId})`。
            // 但是我们没看到后端有 `on('join')` 的处理。
            // 如果后端没有 `on('join')`，那 `emit(room=...)` 只有在 server 端手动把 sid 加入 room 时才有效。
            // 鉴于后端代码未展示 join 逻辑，我们假设：
            // 1. 或者 WebSocketHandler 广播给所有 (broadcast=True) -> 代码显示有 `broadcast_to_all` 但也有 `send_to_task`
            // 2. 或者我们需要在后端加 join 逻辑。
            // 3. 或者前端接收所有广播并过滤。
            // 如果后端代码 `ws_event_handler.py` 里是用 `room=task_id`，那前端必须在那个 room 里。
            // 由于我们之前没有修改后端添加 join event，这可能是一个问题。
            // **修正策略**：前端尝试发送 join 事件（即使后端没显式写，Flask-SocketIO 可能有默认处理？不，通常没有）。
            // 既然我们有权修改后端，为了保险，我们应该在后端添加 `join` 事件处理，或者修改后端为广播所有并带上 task_id。
            // 考虑到"实时看到日志"的要求，最稳妥的是后端广播所有日志，前端根据 task_id 过滤。
            // 但为了性能，room 是最好的。
            // 让我们假设我们需要在后端添加 join 支持。
            // 暂时先往下写，稍后我会在后端补充 socketio.on('join')。
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
            // 初始化编辑状态
            const status = taskStatuses[taskId] || {};
            // 这里应该用当前 Config，但 API 没有直接返回 Config，只能用创建时的或默认的
            // 实际上 Status 接口也没有返回 Config。
            // 我们用 editConfig 的默认值或者上次的值
        } catch (err) {
            alert(`暂停失败: ${err.message}`);
        }
    };

    const handleResume = async (taskId) => {
        try {
            await axios.post(`${API_BASE_URL}/resume/${taskId}`);
            await fetchStatus(taskId);
        } catch (err) {
            alert(`恢复失败: ${err.message}`);
        }
    };

    const handleStop = async (taskId) => {
        try {
            await axios.post(`${API_BASE_URL}/stop/${taskId}`);
            await fetchStatus(taskId);
            // 停止后，runningTaskId 会在轮询中被清除
        } catch (err) {
            alert(`停止失败: ${err.message}`);
        }
    };

    const handleUpdateConfig = async (taskId) => {
        try {
            await axios.post(`${API_BASE_URL}/config/${taskId}`, editConfig);
            alert("配置更新成功！");
        } catch (err) {
            alert(`配置更新失败: ${err.message}`);
        }
    };

    // 渲染
    const currentStatus = selectedTaskId ? taskStatuses[selectedTaskId] : null;
    const isPaused = currentStatus?.status === TASK_STATUS.PAUSED;

    return (
        <div className="crawler-container">
            <div className="sidebar">
                <h2>爬虫任务列表</h2>
                <button className="new-task-btn" onClick={() => setSelectedTaskId(null)}>+ 新建任务</button>
                <ul className="task-list">
                    {tasks.map(task => (
                        <li 
                            key={task.id} 
                            className={selectedTaskId === task.id ? 'active' : ''}
                            onClick={() => setSelectedTaskId(task.id)}
                        >
                            <span className="task-id">{task.id.substring(0, 8)}...</span>
                            <span className={`status-badge ${(taskStatuses[task.id]?.status || 'PENDING').toLowerCase()}`}>
                                {taskStatuses[task.id]?.status || 'PENDING'}
                            </span>
                        </li>
                    ))}
                </ul>
            </div>

            <div className="main-content">
                {!selectedTaskId ? (
                    <div className="create-task-form">
                        <h2>创建新任务</h2>
                        <form onSubmit={handleCreateTask}>
                            <div className="form-group">
                                <label>Start URL:</label>
                                <input 
                                    type="text" 
                                    value={formData.start_url} 
                                    onChange={e => setFormData({...formData, start_url: e.target.value})}
                                    required 
                                />
                            </div>
                            <div className="form-group">
                                <label>Strategy:</label>
                                <select 
                                    value={formData.strategy} 
                                    onChange={e => setFormData({...formData, strategy: e.target.value})}
                                >
                                    <option value="BFS">BFS</option>
                                    <option value="DFS">DFS</option>
                                </select>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Max Depth:</label>
                                    <input 
                                        type="number" 
                                        value={formData.max_depth} 
                                        onChange={e => setFormData({...formData, max_depth: parseInt(e.target.value)})}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Max Pages:</label>
                                    <input 
                                        type="number" 
                                        value={formData.max_pages} 
                                        onChange={e => setFormData({...formData, max_pages: parseInt(e.target.value)})}
                                    />
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Interval (s):</label>
                                <input 
                                    type="number" 
                                    step="0.1" 
                                    value={formData.interval} 
                                    onChange={e => setFormData({...formData, interval: parseFloat(e.target.value)})}
                                />
                            </div>
                            <div className="form-group">
                                <label>Allow Domains (comma separated):</label>
                                <input 
                                    type="text" 
                                    value={formData.allow_domains} 
                                    onChange={e => setFormData({...formData, allow_domains: e.target.value})}
                                    placeholder="example.com, google.com"
                                />
                            </div>
                            <button type="submit" className="submit-btn">创建任务</button>
                        </form>
                    </div>
                ) : (
                    <div className="task-dashboard">
                        <div className="dashboard-header">
                            <h2>任务: {selectedTaskId}</h2>
                            <div className="status-bar">
                                状态: <strong>{currentStatus?.status || 'PENDING'}</strong> | 
                                已访问: {currentStatus?.visited_count || 0} | 
                                队列: {currentStatus?.queue_size || 0}
                            </div>
                        </div>

                        <div className="controls">
                            <button onClick={() => handleStart(selectedTaskId)} disabled={currentStatus?.status === TASK_STATUS.RUNNING || currentStatus?.status === TASK_STATUS.COMPLETED}>开始</button>
                            <button onClick={() => handlePause(selectedTaskId)} disabled={currentStatus?.status !== TASK_STATUS.RUNNING}>暂停</button>
                            <button onClick={() => handleResume(selectedTaskId)} disabled={currentStatus?.status !== TASK_STATUS.PAUSED}>继续</button>
                            <button onClick={() => handleStop(selectedTaskId)} disabled={[TASK_STATUS.STOPPED, TASK_STATUS.COMPLETED, TASK_STATUS.FAILED].includes(currentStatus?.status)}>结束</button>
                        </div>

                        {isPaused && (
                            <div className="config-editor">
                                <h3>修改配置 (暂停中)</h3>
                                <div className="form-row">
                                    <div className="form-group">
                                        <label>Interval:</label>
                                        <input 
                                            type="number" step="0.1" 
                                            value={editConfig.interval}
                                            onChange={e => setEditConfig({...editConfig, interval: parseFloat(e.target.value)})}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Max Pages:</label>
                                        <input 
                                            type="number"
                                            value={editConfig.max_pages}
                                            onChange={e => setEditConfig({...editConfig, max_pages: parseInt(e.target.value)})}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Max Depth:</label>
                                        <input 
                                            type="number"
                                            value={editConfig.max_depth}
                                            onChange={e => setEditConfig({...editConfig, max_depth: parseInt(e.target.value)})}
                                        />
                                    </div>
                                    <button onClick={() => handleUpdateConfig(selectedTaskId)}>更新配置</button>
                                </div>
                            </div>
                        )}

                        <div className="dashboard-content">
                            <LogViewer taskId={selectedTaskId} logs={logs[selectedTaskId] || []} />
                            <ResultViewer results={results[selectedTaskId]} />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CrawlerMain;
