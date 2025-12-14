import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const handlers = {};

const mockSocket = {
  on: vi.fn((event, cb) => {
    handlers[event] = cb;
  }),
  emit: vi.fn(),
  disconnect: vi.fn(),
};

vi.mock("socket.io-client", () => {
  return {
    default: vi.fn(() => mockSocket),
  };
});

vi.mock("axios", () => {
  return {
    default: {
      post: vi.fn(() =>
        Promise.resolve({ data: { task_id: "task-123456" } })
      ),
      get: vi.fn(() => Promise.resolve({ data: [] })),
    },
  };
});

import CrawlerMain from "../frontend/src/features/crawler_main/CrawlerMain.jsx";

describe("CrawlerMain realtime logs", () => {
  it("renders crawl_log messages in LogViewer for selected task", async () => {
    render(<CrawlerMain />);

    const submitBtn = await screen.findByText("启动爬虫");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("实时日志")).toBeDefined();
    });

    const handler = handlers["crawl_log"];
    expect(typeof handler).toBe("function");

    const message = {
      timestamp: "2025-12-14 22:45:23",
      level: "INFO",
      message:
        "✓ 爬取成功: Test Page (深度: 1)\n  URL: https://example.com",
      event_type: "PageCrawledEvent",
      task_id: "task-123456",
      data: {
        url: "https://example.com",
        title: "Test Page",
        depth: 1,
        pdf_count: 0,
      },
      progress: {
        current_depth: 1,
        pages_crawled: 1,
        pdfs_found: 0,
      },
    };

    handler(message);

    await screen.findByText(/Test Page/);
  });
});

