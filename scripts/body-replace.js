// 通用响应体正则替换脚本（用于兼容 QX 的 url response-body <find> response-body <replace>）
let body = $response.body;
if (body && typeof $argument === "string" && $argument) {
  try {
    const cfg = JSON.parse($argument);
    if (cfg && typeof cfg.find === "string") {
      const re = new RegExp(cfg.find, "g");
      body = body.replace(re, cfg.replace ?? "");
    }
  } catch (e) {}
}
$done({ body });
