#!/usr/bin/env node
// 静态守卫：页面入口上不允许有“已推送”假成功文案。
// 只有接口真正入库成功返回时，脚本才允许拼出“已推送”。
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..", "frontend");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const js = fs.readFileSync(path.join(root, "app.js"), "utf8");

let failures = [];

// HTML 是静态入口：任何写死的“已推送”都是假成功文案。
if (html.includes("已推送")) {
  failures.push("index.html 仍含写死的“已推送”入口文案");
}

// 假入口元素不应再存在。
if (/id=["']entry-lead["']/.test(html)) {
  failures.push("index.html 仍保留 #entry-lead 假成功入口");
}
if (html.includes("entryLead") || js.includes("entryLead") || js.includes("entry-lead")) {
  failures.push("app.js 仍引用 entry-lead/entryLead 假成功入口");
}

// 脚本里不允许再把成功文案写死成兜底默认值（那会让被拒也闪出“已推送”）。
if (js.includes('"已推送"') || js.includes("'已推送'") || js.includes("`已推送`")) {
  failures.push("app.js 仍把“已推送”写死为本地默认/兜底文案");
}

if (failures.length) {
  console.error("前端静态守卫失败：");
  for (const f of failures) console.error("  - " + f);
  process.exit(1);
}
console.log("前端静态守卫通过：入口无假“已推送”文案");
