/**
 * AI Developer Growth - 用户行为追踪
 *
 * 追踪指标:
 * - 搜索查询 (搜索词、结果数、点击位置)
 * - 阅读时长 (每页停留时间)
 * - 页面访问 (PV、入口页、跳出率)
 *
 * 数据存储: localStorage (静态站点友好)
 * 隐私: 不发送任何数据到外部服务器，仅本地存储
 */

(function () {
  "use strict";

  const STORAGE_KEY = "adg_tracking";
  const MAX_EVENTS = 1000;
  const READ_TIME_INTERVAL = 5000; // 每 5 秒记录一次阅读时间

  // ── 工具函数 ──────────────────────────────────────

  function getStore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : { searches: [], pageviews: [], reading_time: {} };
    } catch {
      return { searches: [], pageviews: [], reading_time: {} };
    }
  }

  function saveStore(data) {
    try {
      // 限制事件数量，防止 localStorage 溢出
      if (data.searches.length > MAX_EVENTS) {
        data.searches = data.searches.slice(-MAX_EVENTS);
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch {
      // localStorage 满了就静默失败
    }
  }

  function getPagePath() {
    return window.location.pathname.replace(/\/$/, "/") || "/";
  }

  // ── 搜索追踪 ──────────────────────────────────────

  function trackSearch(query, resultCount) {
    const store = getStore();
    store.searches.push({
      q: query,
      results: resultCount,
      ts: Date.now(),
      page: getPagePath(),
    });
    saveStore(store);
  }

  function initSearchTracking() {
    // 监听 MkDocs 搜索
    const searchInput = document.querySelector("[data-md-search-input]");
    if (!searchInput) return;

    let debounceTimer;
    searchInput.addEventListener("input", function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        const query = searchInput.value.trim();
        if (query.length < 2) return;

        // 延迟获取结果数 (MkDocs 搜索是异步的)
        setTimeout(function () {
          const results = document.querySelectorAll(
            "[data-md-search-result]"
          );
          trackSearch(query, results.length);
        }, 300);
      }, 500);
    });
  }

  // ── 阅读时长追踪 ──────────────────────────────────

  function trackReadingTime(seconds) {
    const store = getStore();
    const page = getPagePath();
    if (!store.reading_time[page]) {
      store.reading_time[page] = 0;
    }
    store.reading_time[page] += seconds;
    saveStore(store);
  }

  function initReadingTimeTracking() {
    let startTime = Date.now();
    let intervalId;

    function flush() {
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      if (elapsed > 0) {
        trackReadingTime(elapsed);
      }
    }

    // 定期记录
    intervalId = setInterval(function () {
      flush();
      startTime = Date.now(); // 重置起点
    }, READ_TIME_INTERVAL);

    // 页面离开时记录
    window.addEventListener("beforeunload", flush);

    // 页面可见性变化 (切 tab 等)
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        flush();
        startTime = Date.now();
      }
    });
  }

  // ── 页面访问追踪 ──────────────────────────────────

  function trackPageview() {
    const store = getStore();
    const page = getPagePath();
    store.pageviews.push({
      page: page,
      ts: Date.now(),
      ref: document.referrer || "",
      ua: navigator.userAgent.substring(0, 50),
    });
    saveStore(store);
  }

  // ── 导出追踪数据 (开发者工具) ─────────────────────

  function exportTrackingData() {
    const store = getStore();
    const blob = new Blob([JSON.stringify(store, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "adg-tracking-" + new Date().toISOString().slice(0, 10) + ".json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function getTrackingSummary() {
    const store = getStore();

    // 搜索统计
    const searchTerms = {};
    store.searches.forEach(function (s) {
      searchTerms[s.q] = (searchTerms[s.q] || 0) + 1;
    });
    const topSearches = Object.entries(searchTerms)
      .sort(function (a, b) { return b[1] - a[1]; })
      .slice(0, 10);

    // 阅读时间统计
    const sortedReading = Object.entries(store.reading_time)
      .sort(function (a, b) { return b[1] - a[1]; })
      .slice(0, 10);

    // 页面热度
    const pageCounts = {};
    store.pageviews.forEach(function (p) {
      pageCounts[p.page] = (pageCounts[p.page] || 0) + 1;
    });
    const topPages = Object.entries(pageCounts)
      .sort(function (a, b) { return b[1] - a[1]; })
      .slice(0, 10);

    return {
      total_searches: store.searches.length,
      total_pageviews: store.pageviews.length,
      unique_pages: Object.keys(pageCounts).length,
      top_searches: topSearches,
      top_pages: topPages,
      reading_time: sortedReading,
    };
  }

  // 暴露到全局 (供控制台调试)
  window.adgTracking = {
    export: exportTrackingData,
    summary: getTrackingSummary,
    clear: function () {
      localStorage.removeItem(STORAGE_KEY);
    },
  };

  // ── 初始化 ────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", function () {
    trackPageview();
    initSearchTracking();
    initReadingTimeTracking();

    console.log(
      "[ADG Tracking] 初始化完成。使用 adgTracking.summary() 查看摘要，adgTracking.export() 导出数据。"
    );
  });
})();
