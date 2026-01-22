import os
import requests
import json
import time
from typing import List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class GiteeFolderDownloader:
    def __init__(self, repo_owner: str, repo_name: str, branch: str, token: str = None, cache_file: str = "./download_cache.json"):
        """
        初始化 Gitee 文件夹下载器（含缓存+重试优化，修复更新时间字段问题）
        :param repo_owner: Gitee 仓库所有者（用户名/组织名）
        :param repo_name: 仓库名
        :param branch: 分支名/标签名
        :param token: 个人访问令牌（私有仓库必填）
        :param cache_file: 缓存文件路径（默认 ./download_cache.json）
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self.token = token
        self.cache_file = cache_file

        # Gitee API 基础地址
        self.contents_api = f"https://gitee.com/api/v5/repos/{repo_owner}/{repo_name}/contents"
        self.raw_base_url = f"https://gitee.com/{repo_owner}/{repo_name}/raw/{branch}"

        # 请求头（鉴权+防反爬）
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

        # 初始化带重试机制的 Session
        self.session = self._init_retry_session()

    def _init_retry_session(self) -> requests.Session:
        """初始化带重试机制的请求 Session"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.headers.update(self.headers)
        return session

    def _load_cache(self) -> dict:
        """加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️  缓存文件 {self.cache_file} 损坏，将重新创建")
                os.remove(self.cache_file)
        return {}

    def _save_cache(self, cache_data: dict):
        """保存缓存"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    def _get_file_update_time(self, item: dict) -> str:
        """
        兼容获取 Gitee 文件的更新时间（核心修复点）
        :param item: Gitee API 返回的文件信息
        :return: 标准化的更新时间字符串
        """
        # 优先级：commit.author.date > commit.committer.date > 当前时间（兜底）
        try:
            # 从 commit 中取作者提交时间（Gitee 稳定返回）
            return item["commit"]["author"]["date"]
        except KeyError:
            try:
                return item["commit"]["committer"]["date"]
            except KeyError:
                # 极端情况：用当前时间兜底，避免程序崩溃
                fallback_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                print(f"⚠️  文件 [{item.get('path', '未知文件')}] 未获取到更新时间，使用兜底时间：{fallback_time}")
                return fallback_time

    def _list_files_recursive(self, folder_path: str = "") -> List[dict]:
        """递归获取目标文件夹下所有文件（修复更新时间字段）"""
        files = []
        url = f"{self.contents_api}/{folder_path}" if folder_path else self.contents_api
        params = {"ref": self.branch}

        while url:
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                print(f"❌ 获取文件列表失败：{str(e)}")
                if "403" in str(e) and self.token:
                    print("可能是 Token 无效或权限不足，请检查！")
                return []

            for item in data:
                if item["type"] == "file":
                    # 核心修复：用 _get_file_update_time 获取更新时间
                    files.append({
                        "remote_path": item["path"],
                        "download_url": item["download_url"],
                        "updated_at": self._get_file_update_time(item)
                    })
                elif item["type"] == "dir":
                    # 递归处理子目录
                    sub_files = self._list_files_recursive(item["path"])
                    files.extend(sub_files)

            # 处理分页
            url = response.links.get("next", {}).get("url")
            params = {}

        return files

    def download_folder(self, remote_folder: str, local_save_path: str):
        """下载指定文件夹（含缓存优化）"""
        print(
            f"🔍 正在获取 Gitee 仓库 [{self.repo_owner}/{self.repo_name}] 分支 [{self.branch}] 的文件夹 [{remote_folder}]...")

        # 1. 获取文件列表
        all_files = self._list_files_recursive(remote_folder)
        if not all_files:
            print("⚠️  未找到任何文件（路径/分支错误或权限不足）")
            return

        # 过滤目标文件夹下的文件
        target_files = [f for f in all_files if f["remote_path"].startswith(remote_folder)]
        cache = self._load_cache()
        print(f"✅ 共找到 {len(target_files)} 个文件，开始检查更新...")

        # 2. 分类文件：需下载/未变更
        to_download = []
        unchanged = []
        for file in target_files:
            remote_path = file["remote_path"]
            remote_update_time = file["updated_at"]
            local_update_time = cache.get(remote_path, "")

            if remote_update_time != local_update_time:
                to_download.append(file)
            else:
                unchanged.append(remote_path)

        # 输出未变更文件提示
        if unchanged:
            print(f"ℹ️  {len(unchanged)} 个文件未变更，跳过下载：")
            for path in unchanged[:5]:
                print(f"  - {path}")
            if len(unchanged) > 5:
                print(f"  - 还有 {len(unchanged)-5} 个文件未变更...")

        if not to_download:
            print("\n🎉 所有文件均为最新，无需下载！")
            return

        # 3. 下载新增/更新的文件
        print(f"\n📥 开始下载 {len(to_download)} 个新增/更新文件...")
        for file_info in to_download:
            remote_path = file_info["remote_path"]
            download_url = file_info["download_url"]
            remote_update_time = file_info["updated_at"]

            # 构建本地路径
            local_file_path = os.path.join(local_save_path, remote_path)
            local_dir = os.path.dirname(local_file_path)
            os.makedirs(local_dir, exist_ok=True)

            # 下载文件
            try:
                response = self.session.get(download_url, stream=True)
                response.raise_for_status()
                with open(local_file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ 下载成功：{remote_path}")
                # 更新缓存
                cache[remote_path] = remote_update_time
            except requests.exceptions.RequestException as e:
                print(f"❌ 下载失败：{remote_path} → 错误：{str(e)}")

        # 4. 保存缓存
        self._save_cache(cache)
        print(f"\n🎉 下载完成！本地路径：{os.path.abspath(local_save_path)}")
        print(f"ℹ️  缓存已更新至：{self.cache_file}")


# ------------------- 你的配置（无需修改） -------------------
if __name__ == "__main__":
    REPO_OWNER = "zycisaman"
    REPO_NAME = "sora2-character-repository"
    BRANCH = "master"
    REMOTE_FOLDER = "cache"
    LOCAL_SAVE_PATH = "./"
    GITEE_TOKEN = "797cf3462f79998833ce60eb7f775fa3"

    # 启动下载
    downloader = GiteeFolderDownloader(
        repo_owner=REPO_OWNER,
        repo_name=REPO_NAME,
        branch=BRANCH,
        token=GITEE_TOKEN
    )
    downloader.download_folder(
        remote_folder=REMOTE_FOLDER,
        local_save_path=LOCAL_SAVE_PATH
    )