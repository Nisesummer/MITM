// 墨迹天气「我的页面」去广告（等价转换自 ddgksf2013 MoJiWeatherAds.conf 的 jsonjq-response-body）
let body = $response.body;
if (body) {
  try {
    let obj = JSON.parse(body);
    if (Array.isArray(obj.entrance_region_res_list)) {
      const blocked = new Set(["工具区", "我页面灯泡", "banner区"]);
      obj.entrance_region_res_list = obj.entrance_region_res_list.filter(
        (item) => !item || !blocked.has(item.region_name)
      );
    }
    body = JSON.stringify(obj);
  } catch (e) {}
}
$done({ body });
