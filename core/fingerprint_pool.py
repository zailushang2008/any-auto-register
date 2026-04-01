"""
统一指纹池 - 增强版

所有平台共用的浏览器指纹配置，支持：
- Chrome 多版本（128-137）
- Firefox 多版本
- macOS / Windows / Linux 系统指纹
- HTTP/2 指纹轮换
- sec-ch-ua 动态生成

使用方法：
    from core.fingerprint_pool import get_random_profile, get_chrome_profiles, get_firefox_profiles
"""

import random
import uuid
from typing import Optional


# ==================== Chrome 指纹池 ====================

CHROME_PROFILES = [
    # Chrome 128 (mapped to chrome131 for curl_cffi compatibility)
    {
        "major": 128, "impersonate": "chrome131",
        "build": 6613, "patch_range": (79, 205),
        "sec_ch_ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "platform": "Windows",
    },
    # Chrome 129 (mapped to chrome131 for curl_cffi compatibility)
    {
        "major": 129, "impersonate": "chrome131",
        "build": 6668, "patch_range": (65, 195),
        "sec_ch_ua": '"Google Chrome";v="129", "Chromium";v="129", "Not_A Brand";v="24"',
        "platform": "Windows",
    },
    # Chrome 130 (mapped to chrome131 for curl_cffi compatibility)
    {
        "major": 130, "impersonate": "chrome131",
        "build": 6723, "patch_range": (56, 183),
        "sec_ch_ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "platform": "Windows",
    },
    # Chrome 131
    {
        "major": 131, "impersonate": "chrome131",
        "build": 6778, "patch_range": (69, 205),
        "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": "Windows",
    },
    # Chrome 132 (mapped to chrome133a for curl_cffi compatibility)
    {
        "major": 132, "impersonate": "chrome133a",
        "build": 6834, "patch_range": (50, 190),
        "sec_ch_ua": '"Google Chrome";v="132", "Chromium";v="132", "Not-A.Brand";v="24"',
        "platform": "Windows",
    },
    # Chrome 133
    {
        "major": 133, "impersonate": "chrome133a",
        "build": 6943, "patch_range": (33, 153),
        "sec_ch_ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        "platform": "Windows",
    },
    # Chrome 134 (mapped to chrome136 for curl_cffi compatibility)
    {
        "major": 134, "impersonate": "chrome136",
        "build": 6998, "patch_range": (27, 159),
        "sec_ch_ua": '"Chromium";v="134", "Google Chrome";v="134", "Not.A/Brand";v="24"',
        "platform": "Windows",
    },
    # Chrome 136
    {
        "major": 136, "impersonate": "chrome136",
        "build": 7103, "patch_range": (48, 175),
        "sec_ch_ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "platform": "Windows",
    },
]


# ==================== Firefox 指纹池 ====================

FIREFOX_PROFILES = [
    {
        "major": 128, "impersonate": "firefox128",
        "version": "128.0",
        "platform": "Windows",
    },
    {
        "major": 133, "impersonate": "firefox133",
        "version": "133.0",
        "platform": "Windows",
    },
    {
        "major": 135, "impersonate": "firefox135",
        "version": "135.0",
        "platform": "Windows",
    },
]


# ==================== Safari 指纹池 ====================

SAFARI_PROFILES = [
    {"impersonate": "safari17_0", "version": "17.0", "platform": "macOS"},
    {"impersonate": "safari18_0", "version": "18.0", "platform": "macOS"},
]


# ==================== Accept-Language 池 ====================

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,zh-CN;q=0.8",
    "en-US,en;q=0.8,zh-CN;q=0.7",
    "en,en-US;q=0.9",
    "en-US,en;q=0.8",
    "en-GB,en;q=0.9",
    "en-GB,en-US;q=0.9,en;q=0.8",
    "zh-CN,zh;q=0.9,en;q=0.8",
    "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
]


# ==================== sec-ch-ua-platform 池 ====================

PLATFORM_VALUES = {
    "Windows": '"Windows"',
    "macOS": '"macOS"',
    "Linux": '"Linux"',
}


# ==================== 生成函数 ====================

def _build_ua_windows(profile: dict) -> str:
    """生成 Windows User-Agent"""
    patch = random.randint(*profile["patch_range"])
    full_ver = f"{profile['major']}.0.{profile['build']}.{patch}"
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_ver} Safari/537.36"
    )


def _build_ua_macos(profile: dict) -> str:
    """生成 macOS User-Agent"""
    patch = random.randint(*profile["patch_range"])
    full_ver = f"{profile['major']}.0.{profile['build']}.{patch}"
    mac_ver = random.choice(["10_15_7", "14_0", "14_1", "14_2", "14_3", "14_4", "15_0"])
    return (
        f"Mozilla/5.0 (Macintosh; Intel Mac OS X {mac_ver}) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_ver} Safari/537.36"
    )


def _build_ua_linux(profile: dict) -> str:
    """生成 Linux User-Agent"""
    patch = random.randint(*profile["patch_range"])
    full_ver = f"{profile['major']}.0.{profile['build']}.{patch}"
    return (
        f"Mozilla/5.0 (X11; Linux x86_64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_ver} Safari/537.36"
    )


def get_random_chrome_profile(prefer_newer: bool = True) -> dict:
    """
    获取随机 Chrome 指纹配置
    
    Args:
        prefer_newer: 是否偏好更新的版本（提高权重）
    
    Returns:
        包含 impersonate, major, ua, sec_ch_ua, platform, accept_language 的字典
    """
    if prefer_newer:
        # 偏好新版：132+ 权重更高
        weights = []
        for p in CHROME_PROFILES:
            if p["major"] >= 133:
                weights.append(3)
            elif p["major"] >= 130:
                weights.append(2)
            else:
                weights.append(1)
        profile = random.choices(CHROME_PROFILES, weights=weights, k=1)[0]
    else:
        profile = random.choice(CHROME_PROFILES)

    # 随机选择平台
    platform = random.choice(["Windows", "macOS", "Linux"])
    
    # 根据平台生成 UA
    ua_builders = {
        "Windows": _build_ua_windows,
        "macOS": _build_ua_macos,
        "Linux": _build_ua_linux,
    }
    ua = ua_builders[platform](profile)

    # 为 macOS/Linux 调整 sec-ch-ua（去掉 Google Chrome 前缀变为 Chromium）
    if platform == "macOS":
        sec_ch_ua = profile["sec_ch_ua"]
    elif platform == "Linux":
        # Linux 通常用 Chromium
        sec_ch_ua = profile["sec_ch_ua"].replace("Google Chrome", "Chromium")
    else:
        sec_ch_ua = profile["sec_ch_ua"]

    return {
        "impersonate": profile["impersonate"],
        "major": profile["major"],
        "ua": ua,
        "sec_ch_ua": sec_ch_ua,
        "platform": platform,
        "sec_ch_ua_platform": PLATFORM_VALUES[platform],
        "accept_language": random.choice(ACCEPT_LANGUAGES),
    }


def get_random_firefox_profile() -> dict:
    """获取随机 Firefox 指纹配置"""
    profile = random.choice(FIREFOX_PROFILES)
    ua = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{profile['version']}) Gecko/20100101 Firefox/{profile['version']}"
    return {
        "impersonate": profile["impersonate"],
        "major": profile["major"],
        "ua": ua,
        "platform": profile["platform"],
        "accept_language": random.choice(ACCEPT_LANGUAGES),
    }


def get_random_safari_profile() -> dict:
    """获取随机 Safari 指纹配置"""
    profile = random.choice(SAFARI_PROFILES)
    return {
        "impersonate": profile["impersonate"],
        "ua": None,  # Safari 的 UA 由 curl_cffi 自动处理
        "platform": profile["platform"],
        "accept_language": random.choice(ACCEPT_LANGUAGES),
    }


def get_random_profile(browser: str = "chrome", prefer_newer: bool = True) -> dict:
    """
    获取随机浏览器指纹
    
    Args:
        browser: "chrome" | "firefox" | "safari" | "random"
        prefer_newer: Chrome 是否偏好更新版本
    """
    if browser == "random":
        browser = random.choices(
            ["chrome", "firefox", "safari"],
            weights=[70, 20, 10],  # Chrome 占比最高
            k=1
        )[0]

    if browser == "chrome":
        return get_random_chrome_profile(prefer_newer)
    elif browser == "firefox":
        return get_random_firefox_profile()
    elif browser == "safari":
        return get_random_safari_profile()
    else:
        return get_random_chrome_profile(prefer_newer)


def get_chrome_profiles() -> list:
    """返回所有 Chrome 指纹配置"""
    return CHROME_PROFILES


def get_firefox_profiles() -> list:
    """返回所有 Firefox 指纹配置"""
    return FIREFOX_PROFILES


# ==================== 便捷函数 ====================

def random_device_id() -> str:
    """随机生成设备 ID"""
    return str(uuid.uuid4())


def random_sec_ch_ua_arch() -> str:
    """随机 CPU 架构"""
    return random.choice(['"x86"', '"arm"', '"x86"'])


def random_sec_ch_ua_bitness() -> str:
    """随机位数"""
    return '"64"' if random.random() > 0.1 else '"32"'


def random_sec_ch_ua_model() -> str:
    """随机 model"""
    return '""'


def random_sec_ch_ua_full_version_list() -> dict:
    """生成完整的 sec-ch-ua-full-version-list"""
    profile = get_random_chrome_profile()
    major = profile["major"]
    patch = random.randint(1, 200)
    return {
        "sec-ch-ua-full-version-list": f'"Chromium";v="{major}.0.{6600+major*10}.{patch}", "Google Chrome";v="{major}.0.{6600+major*10}.{patch}", "Not.A/Brand";v="99.0.0.0"',
    }
