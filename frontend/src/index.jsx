import React from "react";
import { createRoot } from "react-dom/client";
import CrawlerMain from "./features/crawler_main/CrawlerMain";

const root = createRoot(document.getElementById("root"));
root.render(<CrawlerMain />);
