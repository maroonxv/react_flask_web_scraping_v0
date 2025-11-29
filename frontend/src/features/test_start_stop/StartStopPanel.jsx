import React, { useEffect, useRef, useState } from "react";

function StartStopPanel() {
  const [startUrl, setStartUrl] = useState("");
  const [strategy, setStrategy] = useState("BFS");
  const [maxDepth, setMaxDepth] = useState(3);
  const [interval, setIntervalMs] = useState(1.0);
  const [allowDomainsInput, setAllowDomainsInput] = useState("");
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const timerRef = useRef(null);

  const start = async () => {
    const allowDomains = allowDomainsInput
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    const body = {
      start_url: startUrl,
      strategy,
      max_depth: Number(maxDepth),
      max_pages: 100,
      interval: Number(interval),
      allow_domains: allowDomains,
    };
    const res = await fetch("/api/crawl/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (res.ok) {
      setTaskId(data.task_id);
    }
  };

  const stop = async () => {
    if (!taskId) return;
    await fetch(`/api/crawl/stop/${taskId}`, { method: "POST" });
  };

  const fetchStatus = async (id) => {
    if (!id) return;
    const res = await fetch(`/api/crawl/status/${id}`);
    const data = await res.json();
    setStatus(data);
  };

  useEffect(() => {
    if (taskId && !timerRef.current) {
      timerRef.current = setInterval(() => fetchStatus(taskId), 2000);
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [taskId]);

  return (
    <div style={{ padding: 16, maxWidth: 640 }}>
      <h3>爬虫控制台</h3>
      <div style={{ display: "grid", gap: 8 }}>
        <input
          placeholder="起始URL"
          value={startUrl}
          onChange={(e) => setStartUrl(e.target.value)}
        />
        <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          <option value="BFS">BFS</option>
          <option value="DFS">DFS</option>
        </select>
        <input
          type="number"
          placeholder="最大深度"
          value={maxDepth}
          onChange={(e) => setMaxDepth(e.target.value)}
        />
        <input
          type="number"
          placeholder="请求间隔(秒)"
          value={interval}
          onChange={(e) => setIntervalMs(e.target.value)}
        />
        <input
          placeholder="允许域名(逗号分隔)"
          value={allowDomainsInput}
          onChange={(e) => setAllowDomainsInput(e.target.value)}
        />
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={start}>开始</button>
          <button onClick={stop} disabled={!taskId}>结束</button>
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <div>任务ID: {taskId || "-"}</div>
        <div>状态: {status?.status || "-"}</div>
        <div>已访问: {status?.visited_count ?? "-"}</div>
        <div>结果数: {status?.result_count ?? "-"}</div>
        <div>队列大小: {status?.queue_size ?? "-"}</div>
        <div>当前深度: {status?.current_depth ?? "-"}</div>
      </div>
    </div>
  );
}

export default StartStopPanel;
