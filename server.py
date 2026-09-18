from __future__ import annotations
import os
from threading import Lock
from typing import Literal
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

mcp = MCPServer("ScienceMuseumControlMock", instructions="科技馆中控 Mock MCP，仅用于 Dify 联调，不连接真实设备。")
lock = Lock()

DEVICES = {
    "EXH_00231": {"deviceId":"EXH_00231","deviceName":"月球车","floor":"二楼","hall":"航天展厅","powerStatus":"OFF","onlineStatus":"ONLINE","maintenanceStatus":"NORMAL"},
    "EXH_00232": {"deviceId":"EXH_00232","deviceName":"火箭发射模拟器","floor":"二楼","hall":"航天展厅","powerStatus":"ON","onlineStatus":"ONLINE","maintenanceStatus":"NORMAL"},
    "EXH_00233": {"deviceId":"EXH_00233","deviceName":"航天发动机演示装置","floor":"二楼","hall":"航天展厅","powerStatus":"ON","onlineStatus":"ONLINE","maintenanceStatus":"NORMAL"},
    "EXH_00301": {"deviceId":"EXH_00301","deviceName":"月球车","floor":"三楼","hall":"未来交通展厅","powerStatus":"ON","onlineStatus":"ONLINE","maintenanceStatus":"NORMAL"},
    "EXH_00110": {"deviceId":"EXH_00110","deviceName":"风洞实验","floor":"一楼","hall":"基础科学展厅","powerStatus":"OFF","onlineStatus":"OFFLINE","maintenanceStatus":"NORMAL"},
    "EXH_00240": {"deviceId":"EXH_00240","deviceName":"宇宙影院","floor":"二楼","hall":"航天展厅","powerStatus":"OFF","onlineStatus":"ONLINE","maintenanceStatus":"MAINTENANCE"},
}

LIGHTS = {
    "LIGHT_0201_01": {"lightId":"LIGHT_0201_01","lightName":"航天展厅主照明","floor":"二楼","hall":"航天展厅","powerStatus":"ON","onlineStatus":"ONLINE"},
    "LIGHT_0201_02": {"lightId":"LIGHT_0201_02","lightName":"航天展厅氛围灯","floor":"二楼","hall":"航天展厅","powerStatus":"OFF","onlineStatus":"ONLINE"},
    "LIGHT_0100_01": {"lightId":"LIGHT_0100_01","lightName":"序厅主照明","floor":"一楼","hall":"序厅","powerStatus":"ON","onlineStatus":"ONLINE"},
}

def _match(v: str, q: str | None) -> bool:
    return True if not q else q.lower() in v.lower()

@mcp.tool()
def search_device(device_name: str, floor: str | None = None, hall: str | None = None) -> dict:
    """根据展品名称、楼层、展厅查询设备。控制前应先用它解析唯一 deviceId。"""
    items = [x for x in DEVICES.values() if _match(x["deviceName"], device_name) and (not floor or x["floor"]==floor) and (not hall or x["hall"]==hall)]
    return {"total": len(items), "devices": items}

@mcp.tool()
def get_device_status(device_id: str) -> dict:
    """查询单个展品设备状态。"""
    if device_id not in DEVICES:
        raise ValueError("DEVICE_NOT_FOUND")
    return DEVICES[device_id]

@mcp.tool()
def control_device(device_id: str, command: Literal["POWER_ON","POWER_OFF","RESTART"]) -> dict:
    """控制单个展品设备。离线或维修设备会拒绝执行。"""
    if device_id not in DEVICES:
        raise ValueError("DEVICE_NOT_FOUND")
    with lock:
        d = DEVICES[device_id]
        if d["maintenanceStatus"] == "MAINTENANCE":
            return {"success":False,"message":"设备处于维修状态，已拒绝控制。","device":d}
        if d["onlineStatus"] == "OFFLINE":
            return {"success":False,"message":"设备当前离线，已拒绝控制。","device":d}
        d["powerStatus"] = "OFF" if command == "POWER_OFF" else "ON"
        return {"success":True,"message":"控制指令执行成功。","command":command,"device":d}

@mcp.tool()
def search_light(keyword: str | None = None, floor: str | None = None, hall: str | None = None) -> dict:
    """查询灯光回路，可按名称、楼层或展厅筛选。"""
    items = [x for x in LIGHTS.values() if (not keyword or _match(x["lightName"], keyword)) and (not floor or x["floor"]==floor) and (not hall or x["hall"]==hall)]
    return {"total":len(items),"lights":items}

@mcp.tool()
def get_light_status(light_id: str) -> dict:
    """查询单个灯光回路状态。"""
    if light_id not in LIGHTS:
        raise ValueError("LIGHT_NOT_FOUND")
    return LIGHTS[light_id]

@mcp.tool()
def control_light(command: Literal["POWER_ON","POWER_OFF"], light_id: str | None = None, floor: str | None = None, hall: str | None = None) -> dict:
    """控制单个或按区域控制灯光。"""
    if not light_id and not floor and not hall:
        raise ValueError("必须提供 light_id 或 floor/hall")
    changed = []
    with lock:
        for x in LIGHTS.values():
            if light_id and x["lightId"] != light_id: continue
            if floor and x["floor"] != floor: continue
            if hall and x["hall"] != hall: continue
            if x["onlineStatus"] != "ONLINE": continue
            x["powerStatus"] = "ON" if command == "POWER_ON" else "OFF"
            changed.append(x.copy())
    return {"success":bool(changed),"affected":len(changed),"lights":changed}

@mcp.tool()
def get_operation_overview(floor: str | None = None, hall: str | None = None) -> dict:
    """获取楼层/展厅运行概览，供大模型进行运行情况分析。"""
    ds = [x for x in DEVICES.values() if (not floor or x["floor"]==floor) and (not hall or x["hall"]==hall)]
    alarms = []
    if (not floor or floor=="二楼") and (not hall or hall=="航天展厅"):
        alarms = [{"exhibitName":"航天发动机演示装置","circuitName":"回路2","type":"LEAKAGE_CURRENT","level":"WARNING","value":18.6,"unit":"mA"}]
    env = {"temperatureWarnings":[],"humidityWarnings":[],"smokeAlarms":[]}
    if not floor or floor=="二楼":
        env["temperatureWarnings"]=[{"hall":"航天展厅","pointName":"宇宙影院环境监测点","temperature":31.8,"level":"WARNING"}]
    return {
        "scope": hall or floor or "全馆",
        "exhibits":{
            "total":len(ds),
            "running":sum(1 for x in ds if x["powerStatus"]=="ON" and x["onlineStatus"]=="ONLINE"),
            "off":sum(1 for x in ds if x["powerStatus"]=="OFF"),
            "offline":sum(1 for x in ds if x["onlineStatus"]=="OFFLINE"),
            "maintenance":sum(1 for x in ds if x["maintenanceStatus"]=="MAINTENANCE"),
        },
        "circuits":{"abnormalCount":len(alarms),"abnormalItems":alarms},
        "environment":env,
        "alarms":alarms,
        "summaryHint":"仅根据返回数据分析，不要虚构故障原因。"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )
