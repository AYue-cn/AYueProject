from bs4 import BeautifulSoup
import os
import re
import threading
import json
import hashlib  # 用于内容哈希去重
from tkinter import Tk, Frame, Button, Text, Scrollbar, Label, filedialog, messagebox, StringVar, Entry, Radiobutton
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import sys
import time
import urllib.request
from datetime import datetime  # 正确导入datetime类


# ===================== 定制化解析函数（适配霜月短文页面） =====================
def extract_single_chapter(html_content, debug=False):
    """
    定制化解析：适配霜月短文页面结构（透视狂兵）
    返回值：(chapter_title, chapter_content, novel_title)
    章节内容不含标题，避免重复
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    chapter_paragraphs = []  # 存储章节内容段落（不含标题）
    chapter_title = "未知章节"
    novel_title = "未知小说"

    if debug:
        print("=== 调试模式：开始解析霜月短文页面 ===")

    # 步骤1：提取小说标题（从隐藏元素bookname）
    bookname_tag = soup.find('div', id='bookname')
    if bookname_tag:
        novel_title = bookname_tag.get_text(strip=True)
        if debug:
            print(f"✅ 提取小说标题：{novel_title}")

    # 步骤2：提取章节标题（第一个有内容的id="concent"标签）
    concent_tags = soup.find_all('p', id='concent')
    for tag in concent_tags:
        tag_text = tag.get_text(strip=True)
        if tag_text and len(tag_text) > 5:  # 过滤空标签和过短文本
            chapter_title = tag_text
            if debug:
                print(f"✅ 提取章节标题：{chapter_title}")
            break

    # 步骤3：提取所有有效章节内容（class="chapter-text"下的p标签，不含标题）
    chapter_text_divs = soup.find_all('div', class_='chapter-text')
    if debug:
        print(f"✅ 找到 {len(chapter_text_divs)} 个内容容器")

    for div in chapter_text_divs:
        p_tags = div.find_all('p')
        for p in p_tags:
            para_text = p.get_text(strip=True)
            # 过滤条件：
            # 1. 非空且长度≥2
            # 2. 不是章节标题（避免重复）
            # 3. 不包含控制相关文本
            if not para_text or len(para_text) < 2:
                continue
            if para_text == chapter_title:
                continue
            if any(keyword in para_text for keyword in
                   ['客服QQ', '刷新无效', '联系我们', '下一章', '上一章', '目录', '关闭']):
                if debug:
                    print(f"过滤无关文本：{para_text[:20]}...")
                continue
            # 过滤纯数字或特殊字符的无意义段落
            if re.match(r'^[\d\s\W]+$', para_text):
                continue
            chapter_paragraphs.append(para_text)

    if debug:
        print(f"✅ 提取有效段落数：{len(chapter_paragraphs)}")
        if chapter_paragraphs:
            print(f"第一段内容：{chapter_paragraphs[0]}")
            print(f"最后一段内容：{chapter_paragraphs[-1]}")

    # 步骤4：拼接章节内容（仅段落，不含标题）
    if chapter_paragraphs:
        chapter_content = '\n'.join(chapter_paragraphs)
        # 清理多余空行
        chapter_content = re.sub(r'\n+', '\n', chapter_content)
        return chapter_title.strip(), chapter_content.strip(), novel_title
    else:
        if debug:
            print("❌ 未提取到有效章节内容")
        return chapter_title.strip(), None, novel_title


# ===================== 辅助函数（内容去重） =====================
def get_content_hash(content):
    """计算内容的MD5哈希值，用于精准去重"""
    md5 = hashlib.md5()
    md5.update(content.encode('utf-8'))
    return md5.hexdigest()


# =====================================================================

def extract_chapter_number(title_or_html):
    """优化：从章节标题或HTML中提取章节号（增加多规则匹配）"""
    # 规则1：匹配「第X章」「第X话」「第X节」
    patterns = [
        r'第\s*(\d+)\s*章',
        r'第\s*(\d+)\s*话',
        r'第\s*(\d+)\s*节',
        r'第(\d+)章',  # 无空格版本
        r'(\d+)\s*章'  # 无「第」字版本
    ]
    for pattern in patterns:
        match = re.search(pattern, title_or_html)
        if match:
            return int(match.group(1))

    # 规则2：从隐藏元素chapterid提取（备用）
    try:
        soup = BeautifulSoup(title_or_html, 'html.parser')
        chapterid_tag = soup.find('div', id='chapterid')
        if chapterid_tag:
            chapter_id = chapterid_tag.get_text(strip=True)
            if chapter_id.isdigit():
                return int(chapter_id)
    except:
        pass

    # 规则3：从章节标题末尾提取数字（兜底）
    try:
        # 匹配标题末尾的连续数字（如「初入都市123」→ 123）
        end_match = re.search(r'(\d+)\s*$', title_or_html)
        if end_match:
            return int(end_match.group(1))
    except:
        pass

    return 9999  # 未提取到章节号时返回大数字，排在最后


def check_internet_connection():
    """检查网络连接"""
    try:
        urllib.request.urlopen('https://developer.microsoft.com', timeout=5)
        return True
    except:
        try:
            urllib.request.urlopen('https://www.baidu.com', timeout=5)
            return True
        except:
            return False


def get_edge_version():
    """获取本地Edge浏览器版本（用于手动下载驱动）"""
    try:
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"
        ]

        for path in edge_paths:
            path = os.path.expandvars(path)
            if os.path.exists(path):
                import win32api
                info = win32api.GetFileVersionInfo(path, "\\")
                ms = info['FileVersionMS']
                ls = info['FileVersionLS']
                version = f"{(ms >> 16) & 0xffff}.{(ms >> 0) & 0xffff}.{(ls >> 16) & 0xffff}"
                return version[:-1]
        return "未知版本"
    except:
        return "未知版本"


def load_cookies_from_file(driver, cookie_file):
    """从JSON文件加载Cookie到浏览器"""
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)

        # 先访问网站域名（必须先打开网站才能设置Cookie）
        if cookies:
            first_cookie = cookies[0]
            domain = first_cookie.get('domain', '')
            if domain.startswith('.'):
                domain = domain[1:]
            if domain:
                base_url = f"https://{domain}" if not domain.startswith('http') else domain
                driver.get(base_url)
                time.sleep(2)

        # 导入所有Cookie
        cookie_count = 0
        for cookie in cookies:
            cookie_clean = {}
            for key in ['name', 'value', 'domain', 'path', 'expiry', 'secure', 'httpOnly']:
                if key in cookie:
                    cookie_clean[key] = cookie['value'] if key == 'value' else cookie[key]

            try:
                driver.add_cookie(cookie_clean)
                cookie_count += 1
            except Exception as e:
                continue

        return cookie_count
    except Exception as e:
        print(f"加载Cookie失败：{str(e)}")
        return 0


def load_cookies_from_string(driver, cookie_string, domain):
    """从Cookie字符串加载Cookie到浏览器"""
    try:
        # 先访问网站域名
        if domain:
            base_url = f"https://{domain}" if not domain.startswith('http') else domain
            driver.get(base_url)
            time.sleep(2)

        # 解析Cookie字符串（格式：name1=value1; name2=value2; ...）
        cookie_pairs = cookie_string.split(';')
        cookies = []
        for pair in cookie_pairs:
            pair = pair.strip()
            if '=' not in pair:
                continue
            name, value = pair.split('=', 1)
            if name and value:
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': domain.lstrip('http://').lstrip('https://').lstrip('www.'),
                    'path': '/',
                    'secure': False,
                    'httpOnly': False
                })

        # 导入Cookie
        cookie_count = 0
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
                cookie_count += 1
            except Exception as e:
                continue

        return cookie_count
    except Exception as e:
        print(f"从字符串加载Cookie失败：{str(e)}")
        return 0


class NovelCaptureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("小说批量捕获工具 - 霜月短文专用版（自动追加保存）")
        self.root.geometry("1000x780")

        # 初始化变量
        self.driver = None
        # 存储结构：(章节号, 章节标题, 章节内容, 内容哈希) → 新增哈希用于去重
        self.captured_chapters = []
        self.debug_mode = False
        self.driver_path = None
        self.cookie_file = None
        self.cookie_string = ""
        self.cookie_domain = ""
        self.cookie_mode = StringVar(value="file")
        self.novel_title = "未知小说"

        # 自动保存相关变量
        self.save_path = None
        self.auto_save_enabled = False

        # 日志相关
        self.progress_text = None

        # 创建GUI界面
        self.create_ui()

    def create_ui(self):
        # Cookie配置区
        cookie_frame = Frame(self.root, bd=2, relief='groove')
        cookie_frame.pack(fill='x', padx=10, pady=8)

        Label(cookie_frame, text="Cookie免登录配置：", fg="darkgreen", font=("Arial", 10, "bold")).pack(side='left',
                                                                                                       padx=5)
        Radiobutton(cookie_frame, text="JSON文件导入", variable=self.cookie_mode, value="file",
                    command=self.switch_cookie_mode).pack(side='left', padx=5)
        Radiobutton(cookie_frame, text="手动输入Cookie", variable=self.cookie_mode, value="string",
                    command=self.switch_cookie_mode).pack(side='left', padx=5)

        # JSON文件导入区域
        self.file_cookie_frame = Frame(cookie_frame)
        self.cookie_path_var = StringVar()
        self.cookie_entry = Entry(self.file_cookie_frame, textvariable=self.cookie_path_var, width=50)
        self.cookie_entry.pack(side='left', padx=5)
        self.select_cookie_btn = Button(self.file_cookie_frame, text="选择Cookie文件", command=self.select_cookie_file)
        self.select_cookie_btn.pack(side='left', padx=5)

        # 手动输入Cookie区域
        self.string_cookie_frame = Frame(cookie_frame)
        Label(self.string_cookie_frame, text="Cookie字符串：").pack(side='left', padx=5)
        self.cookie_string_var = StringVar()
        self.cookie_string_entry = Entry(self.string_cookie_frame, textvariable=self.cookie_string_var, width=40)
        self.cookie_string_entry.pack(side='left', padx=5)
        Label(self.string_cookie_frame, text="网站域名：").pack(side='left', padx=5)
        self.cookie_domain_var = StringVar()
        self.cookie_domain_entry = Entry(self.string_cookie_frame, textvariable=self.cookie_domain_var, width=20)
        self.cookie_domain_entry.pack(side='left', padx=5)

        # 驱动配置区
        driver_frame = Frame(self.root)
        driver_frame.pack(fill='x', padx=10, pady=5)
        Label(driver_frame, text="Edge驱动配置（网络失败时使用）：", fg="darkred").pack(side='left', padx=5)
        self.driver_path_var = StringVar()
        self.driver_entry = Entry(driver_frame, textvariable=self.driver_path_var, width=50)
        self.driver_entry.pack(side='left', padx=5)
        Button(driver_frame, text="选择驱动文件", command=self.select_driver_file).pack(side='left', padx=5)

        # 顶部控制区
        control_frame = Frame(self.root)
        control_frame.pack(fill='x', padx=10, pady=10)

        self.browser_status = StringVar(value="Edge浏览器未启动")
        status_label = Label(control_frame, textvariable=self.browser_status, fg="red")
        status_label.pack(side='left', padx=10)

        self.start_browser_btn = Button(control_frame, text="自动启动（需网络）", command=self.start_browser_auto)
        self.start_browser_btn.pack(side='left', padx=5)
        self.start_browser_manual_btn = Button(control_frame, text="手动启动（离线）", command=self.start_browser_manual,
                                               bg='#2196F3')
        self.start_browser_manual_btn.pack(side='left', padx=5)
        self.stop_browser_btn = Button(control_frame, text="关闭Edge浏览器", command=self.stop_browser,
                                       state='disabled')
        self.stop_browser_btn.pack(side='left', padx=5)

        Label(control_frame, text=" | ", fg="gray").pack(side='left', padx=5)
        self.capture_btn = Button(control_frame, text="捕获当前章节", command=self.capture_current_chapter,
                                  state='disabled', bg='#4CAF50', fg='white')
        self.capture_btn.pack(side='left', padx=5)
        self.capture_full_page_btn = Button(control_frame, text="捕获完整页面内容",
                                            command=self.capture_full_page_content, state='disabled', bg='#FF9800',
                                            fg='white')
        self.capture_full_page_btn.pack(side='left', padx=5)
        self.change_save_path_btn = Button(control_frame, text="重新选择保存路径", command=self.select_save_path,
                                           state='disabled', bg='#9C27B0', fg='white')
        self.change_save_path_btn.pack(side='left', padx=5)
        self.save_btn = Button(control_frame, text="最终整理保存", command=self.final_save, state='disabled',
                               bg='#f44336', fg='white')
        self.save_btn.pack(side='left', padx=5)

        debug_check = Button(control_frame, text="开启调试", command=self.toggle_debug, bg='#ffc107')
        debug_check.pack(side='right', padx=10)

        # 中间状态显示区
        status_frame = Frame(self.root)
        status_frame.pack(fill='both', padx=10, pady=5)
        Label(status_frame, text="捕获进度/调试信息：").pack(anchor='w')
        self.progress_text = Text(status_frame, height=12, width=110)
        scrollbar = Scrollbar(status_frame, command=self.progress_text.yview)
        self.progress_text.configure(yscrollcommand=scrollbar.set)
        self.progress_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 切换Cookie模式
        self.switch_cookie_mode()

        # 底部提示区
        tip_frame = Frame(self.root)
        tip_frame.pack(fill='x', padx=10, pady=10)
        Label(tip_frame, text="📌 自动追加保存说明：", fg="darkgreen", font=("Arial", 10, "bold")).pack(anchor='w',
                                                                                                      pady=3)
        Label(tip_frame, text="  1. 捕获第一章时将提示选择保存路径，创建TXT文件", fg="darkgreen").pack(anchor='w')
        Label(tip_frame, text="  2. 后续每章捕获成功后自动追加到同一文件，无需手动保存", fg="darkgreen").pack(anchor='w')
        Label(tip_frame, text="  3. 自动去重：同一章节（内容相同）不会重复捕获", fg="darkgreen").pack(anchor='w')
        Label(tip_frame, text="  4. 最终整理：自动过滤重复章节，按章节号排序（保留原标题序号）", fg="darkgreen").pack(
            anchor='w')

        Label(tip_frame, text="📌 霜月短文专用说明：", fg="darkorange", font=("Arial", 10, "bold")).pack(anchor='w',
                                                                                                       pady=3)
        Label(tip_frame, text="  1. 支持小说：透视狂兵（自动识别标题和章节）", fg="darkorange").pack(anchor='w')
        Label(tip_frame, text="  2. 自动提取：章节标题（含序号）+完整内容（过滤广告和控制文本）", fg="darkorange").pack(
            anchor='w')
        Label(tip_frame, text="  3. 使用步骤：启动浏览器→登录→打开小说页→点击「捕获当前章节」", fg="darkorange").pack(
            anchor='w')

        # 状态提示
        net_status = "✅ 网络正常" if check_internet_connection() else "❌ 无网络连接"
        self.net_status_var = StringVar(value=f"网络状态：{net_status}")
        Label(tip_frame, textvariable=self.net_status_var, fg="green" if check_internet_connection() else "red").pack(
            anchor='w', pady=2)
        edge_version = get_edge_version()
        Label(tip_frame, text=f"本地Edge版本：{edge_version}（驱动需对应此版本）", fg="blue").pack(anchor='w', pady=2)

        # Cookie获取教程
        Label(tip_frame, text="Cookie获取教程：", fg="darkblue", font=("Arial", 10, "bold")).pack(anchor='w', pady=2)
        Label(tip_frame, text="  方法1（JSON文件）：F12→应用→Cookie→复制名称/值→按模板创建JSON文件", fg="blue").pack(
            anchor='w')
        Label(tip_frame, text="  方法2（手动输入）：F12→应用→Cookie→复制所有Cookie（格式：name1=value1; name2=value2）",
              fg="blue").pack(anchor='w')
        Label(tip_frame, text="  网站域名示例：txsm.com 或 fbook.net（从浏览器地址栏复制）", fg="blue").pack(anchor='w')

    def switch_cookie_mode(self):
        """切换Cookie导入模式"""
        if self.cookie_mode.get() == "file":
            self.string_cookie_frame.pack_forget()
            self.file_cookie_frame.pack(side='left', padx=10)
            self.log("✅ Cookie模式：JSON文件导入")
        else:
            self.file_cookie_frame.pack_forget()
            self.string_cookie_frame.pack(side='left', padx=10)
            self.log("✅ Cookie模式：手动输入Cookie")

    def select_cookie_file(self):
        """选择Cookie文件（JSON格式）"""
        file_path = filedialog.askopenfilename(
            title="选择Cookie文件（JSON格式）",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            self.cookie_path_var.set(file_path)
            self.cookie_file = file_path
            self.log(f"已选择Cookie文件：{os.path.basename(file_path)}")

    def select_driver_file(self):
        """选择手动下载的Edge驱动文件"""
        file_path = filedialog.askopenfilename(
            title="选择Edge驱动文件（msedgedriver.exe）",
            filetypes=[("可执行文件", "msedgedriver.exe"), ("所有文件", "*.*")]
        )
        if file_path:
            self.driver_path_var.set(file_path)
            self.driver_path = file_path
            self.log(f"已选择手动驱动：{os.path.basename(file_path)}")

    def select_save_path(self):
        """选择保存路径（用于第一次捕获或重新选择）"""
        default_filename = f"{self.novel_title}_自动保存.txt" if self.novel_title != "未知小说" else "小说自动保存.txt"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="选择小说保存路径",
            initialfile=default_filename
        )
        if save_path:
            self.save_path = save_path
            self.auto_save_enabled = True
            self.change_save_path_btn.config(state='normal')
            self.log(f"✅ 保存路径已设置：{self.save_path}")
            self.log("📌 后续捕获的章节将自动追加到该文件（自动去重）")

            # 批量追加已捕获章节（去重后）
            if self.captured_chapters:
                if messagebox.askyesno("提示",
                                       f"已捕获{len(self.captured_chapters)}章内容，是否立即追加到新文件？（会自动去重）"):
                    self.batch_append_chapters()

    def toggle_debug(self):
        self.debug_mode = not self.debug_mode
        self.log(f"调试模式{'已开启' if self.debug_mode else '已关闭'}")

    def start_browser_common(self, driver_service):
        """浏览器启动公共逻辑"""
        try:
            edge_options = Options()
            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            edge_options.add_experimental_option('useAutomationExtension', False)
            edge_options.add_argument('--disable-blink-features=AutomationControlled')
            edge_options.add_argument('--no-sandbox')
            edge_options.add_argument('--disable-dev-shm-usage')
            edge_options.add_argument('--disable-web-security')
            edge_options.add_argument('--allow-running-insecure-content')

            self.driver = webdriver.Edge(service=driver_service, options=edge_options)
            self.driver.implicitly_wait(15)
            self.driver.set_page_load_timeout(30)

            # 加载Cookie
            cookie_count = 0
            if self.cookie_mode.get() == "file" and self.cookie_path_var.get():
                self.log("正在从JSON文件导入Cookie...")
                cookie_count = load_cookies_from_file(self.driver, self.cookie_path_var.get())
            elif self.cookie_mode.get() == "string" and self.cookie_string_var.get() and self.cookie_domain_var.get():
                self.log("正在从手动输入导入Cookie...")
                cookie_count = load_cookies_from_string(
                    self.driver,
                    self.cookie_string_var.get(),
                    self.cookie_domain_var.get()
                )

            if cookie_count > 0:
                self.log(f"✅ 成功导入 {cookie_count} 个Cookie，已自动登录")
            elif self.cookie_mode.get() in ["file", "string"]:
                self.log("⚠️ Cookie导入失败，请检查Cookie配置是否正确")
                messagebox.showwarning("Cookie警告", "Cookie导入失败，请检查配置是否正确")

            # 更新UI状态
            self.browser_status.set("Edge浏览器已启动 ✅")
            self.start_browser_btn.config(state='disabled')
            self.start_browser_manual_btn.config(state='disabled')
            self.stop_browser_btn.config(state='normal')
            self.capture_btn.config(state='normal')
            self.capture_full_page_btn.config(state='normal')
            if self.auto_save_enabled:
                self.change_save_path_btn.config(state='normal')
            self.save_btn.config(state='normal')
            self.log("✅ Edge浏览器启动成功，请手动打开小说第一章页面")
            return True

        except Exception as e:
            error_msg = str(e)[:150] + "..." if len(str(e)) > 150 else str(e)
            self.log(f"❌ 浏览器启动失败：{error_msg}")
            return False

    def start_browser_auto(self):
        """自动模式：自动下载驱动并启动Edge（需网络）"""
        if not check_internet_connection():
            messagebox.showwarning("警告", "当前无网络连接，无法自动下载驱动！请使用手动模式。")
            return

        try:
            self.log("正在自动下载匹配的Edge驱动...（请耐心等待）")
            driver_service = Service(EdgeChromiumDriverManager().install())
            success = self.start_browser_common(driver_service)
            if not success:
                messagebox.showerror("自动启动失败", "启动失败，请检查网络或使用手动模式")
        except Exception as e:
            error_msg = str(e)[:150] + "..." if len(str(e)) > 150 else str(e)
            messagebox.showerror("自动启动失败",
                                 f"启动失败：{error_msg}\n\n建议：\n1. 检查网络连接\n2. 关闭防火墙/杀毒软件\n3. 使用手动模式")

    def start_browser_manual(self):
        """手动模式：使用本地驱动启动Edge（离线可用）"""
        if not self.driver_path:
            messagebox.showwarning("警告", "请先选择手动下载的Edge驱动文件（msedgedriver.exe）！")
            return

        if not os.path.exists(self.driver_path):
            messagebox.showerror("错误", "选择的驱动文件不存在！请重新选择。")
            return

        try:
            self.log(f"正在使用本地驱动启动：{os.path.basename(self.driver_path)}")
            driver_service = Service(self.driver_path)
            success = self.start_browser_common(driver_service)
            if not success:
                messagebox.showerror("手动启动失败", "启动失败，请检查驱动版本或权限")
        except Exception as e:
            error_msg = str(e)[:150] + "..." if len(str(e)) > 150 else str(e)
            messagebox.showerror("手动启动失败",
                                 f"启动失败：{error_msg}\n\n可能原因：\n1. 驱动版本与Edge浏览器版本不匹配\n2. 驱动文件已损坏\n3. 缺少管理员权限")

    def stop_browser(self):
        """关闭Edge浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                self.browser_status.set("Edge浏览器已关闭")
                self.start_browser_btn.config(state='normal')
                self.start_browser_manual_btn.config(state='normal')
                self.stop_browser_btn.config(state='disabled')
                self.capture_btn.config(state='disabled')
                self.capture_full_page_btn.config(state='disabled')
                if not self.auto_save_enabled:
                    self.change_save_path_btn.config(state='disabled')
                if not self.captured_chapters:
                    self.save_btn.config(state='disabled')
                self.log("✅ Edge浏览器已关闭")
            except Exception as e:
                messagebox.showerror("错误", f"关闭Edge浏览器失败：{str(e)}")

    def capture_current_chapter(self):
        """捕获当前浏览器页面的小说章节（自动追加保存+强化去重）"""
        if not self.driver:
            messagebox.showwarning("警告", "请先启动Edge浏览器！")
            return

        capture_thread = threading.Thread(target=self._capture_thread)
        capture_thread.daemon = True
        capture_thread.start()

    def _capture_thread(self):
        """捕获线程：强化去重逻辑"""
        self.root.after(0, lambda: self.capture_btn.config(state='disabled', text='捕获中...'))
        self.log("🔍 开始捕获当前章节（霜月短文专用解析+内容去重）...")

        try:
            # 等待页面完全加载
            self.log("⌛ 等待页面完全加载...")
            WebDriverWait(self.driver, 20).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(3)

            # 获取页面源码
            self.log("📥 获取页面源码...")
            page_source = self.driver.page_source

            # 调试模式：保存页面源码
            if self.debug_mode:
                debug_file = f"debug_page_{int(time.time())}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page_source)
                self.log(f"📁 调试模式：页面源码已保存到 {debug_file}")

            # 解析章节内容
            self.log("🔧 开始解析章节内容...")
            chapter_title, chapter_content, novel_title = extract_single_chapter(page_source, self.debug_mode)

            # 检查有效内容
            if not chapter_content:
                self.log("❌ 捕获失败：未提取到有效章节内容")
                tips = """
排查建议：
1. 确认页面已完全加载（手动刷新后重试）
2. 确认当前页面是小说阅读页（不是目录/登录页）
3. 开启调试模式，查看保存的页面源码是否正常
4. 检查是否需要登录（Cookie是否生效，页面是否显示已登录）
                """
                self.log(tips)
                self.root.after(0, lambda: messagebox.showwarning("捕获失败", f"未提取到有效章节内容\n{tips}"))
                return

            # 更新小说标题
            if self.novel_title == "未知小说" and novel_title != "未知小说":
                self.novel_title = novel_title
                self.log(f"📚 识别小说标题：{self.novel_title}")

                # 首次捕获提示选择保存路径
                if not self.auto_save_enabled:
                    self.log("📌 首次捕获，正在提示选择保存路径...")
                    self.root.after(0, self.select_save_path)
                    # 等待用户选择路径（最多60秒）
                    for _ in range(60):
                        if self.auto_save_enabled:
                            break
                        time.sleep(1)
                    if not self.auto_save_enabled:
                        self.log("❌ 用户取消了保存路径选择，章节未保存")
                        self.root.after(0, lambda: messagebox.showwarning("警告", "未选择保存路径，章节内容未保存！"))
                        return

            # 提取章节号和内容哈希（用于去重）
            chapter_num = extract_chapter_number(page_source)
            content_hash = get_content_hash(chapter_content)  # 内容哈希去重
            self.log(f"📊 章节信息：编号={chapter_num}，标题={chapter_title}，内容哈希={content_hash[:8]}...")

            # 强化去重检查（3重校验）
            duplicate = False
            for num, title, content, hash_val in self.captured_chapters:
                # 1. 章节号+标题完全匹配
                if num == chapter_num and title == chapter_title:
                    self.log(f"⚠️  重复检测：章节号+标题匹配（{num}-{title}）")
                    duplicate = True
                    break
                # 2. 内容哈希完全匹配（最精准）
                if hash_val == content_hash:
                    self.log(f"⚠️  重复检测：内容哈希匹配（{hash_val[:8]}...）")
                    duplicate = True
                    break
                # 3. 内容前200字符匹配（防止哈希碰撞）
                if content[:200] == chapter_content[:200]:
                    self.log(f"⚠️  重复检测：内容前缀匹配")
                    duplicate = True
                    break

            if duplicate:
                self.log(f"⚠️  已捕获过该章节：{chapter_title}，跳过重复捕获")
                self.root.after(0, lambda: messagebox.showinfo("提示", "已捕获过该章节（内容重复），跳过重复内容"))
                return

            # 添加到捕获列表（包含哈希值）
            self.captured_chapters.append((chapter_num, chapter_title, chapter_content, content_hash))
            self.log(f"✅ 已添加到捕获列表，当前累计：{len(self.captured_chapters)} 章（无重复）")

            # 自动追加保存到文件
            self.auto_append_chapter(chapter_title, chapter_content)

            # 更新UI提示
            self.log(f"✅ 捕获成功：【{chapter_title}】")
            self.log(f"   章节长度：{len(chapter_content)} 字符")
            self.log(f"   📥 已自动追加到文件：{self.save_path}")

            self.root.after(0, lambda: messagebox.showinfo("成功",
                                                           f"捕获章节：{chapter_title}\n小说标题：{self.novel_title}\n共{len(chapter_content)}字符\n✅ 已自动追加到文件（无重复）"))

        except Exception as e:
            error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
            self.log(f"❌ 捕获异常：{error_msg}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"捕获失败：{error_msg}"))
        finally:
            self.root.after(0, lambda: self.capture_btn.config(state='normal', text='捕获当前章节'))

    def auto_append_chapter(self, chapter_title, chapter_content):
        """自动追加章节到文件（标题仅保存一次，保留原标题序号）"""
        if not self.auto_save_enabled or not self.save_path:
            self.log("❌ 自动保存未启用，无法追加章节")
            return

        try:
            # 格式化章节内容（直接使用原标题，保留自带序号）
            formatted_content = f"\n{'=' * 80}\n{chapter_title}\n{'=' * 80}\n{chapter_content}\n"

            # 追加到文件
            with open(self.save_path, 'a', encoding='utf-8') as f:
                # 第一个章节写入小说标题
                if len(self.captured_chapters) == 1:
                    f.write(f"📚 {self.novel_title}\n{'=' * 80}\n")
                f.write(formatted_content)

            self.log(f"✅ 章节已成功追加到文件（保留原标题序号）")
        except Exception as e:
            error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
            self.log(f"❌ 追加文件失败：{error_msg}")
            self.root.after(0, lambda: messagebox.showerror("保存错误",
                                                            f"章节内容捕获成功，但追加文件失败：{error_msg}\n\n请检查文件是否被占用或路径是否可写"))

    def batch_append_chapters(self):
        """批量追加已捕获的章节到文件（去重后，保留原标题序号）"""
        if not self.auto_save_enabled or not self.save_path or not self.captured_chapters:
            return

        try:
            # 批量追加前先去重
            self.log(f"📥 开始批量追加{len(self.captured_chapters)}章内容（先去重）...")
            deduplicated = self.deduplicate_chapters(self.captured_chapters)
            if len(deduplicated) < len(self.captured_chapters):
                self.log(f"⚠️  批量追加时过滤了 {len(self.captured_chapters) - len(deduplicated)} 个重复章节")

            # 按章节号排序
            sorted_chapters = sorted(deduplicated, key=lambda x: x[0])

            with open(self.save_path, 'w', encoding='utf-8') as f:
                # 写入小说标题
                f.write(f"📚 {self.novel_title}\n{'=' * 80}\n")

                # 批量写入所有章节（直接使用原标题，保留自带序号）
                for _, chapter_title, chapter_content, _ in sorted_chapters:
                    formatted_content = f"\n{'=' * 80}\n{chapter_title}\n{'=' * 80}\n{chapter_content}\n"
                    f.write(formatted_content)

            self.log(f"✅ 批量追加完成：{self.save_path}（共{len(sorted_chapters)}章，无重复，保留原标题序号）")
            messagebox.showinfo("成功", f"已将{len(sorted_chapters)}章内容批量追加到新文件！（已自动去重，保留原标题序号）")
        except Exception as e:
            error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
            self.log(f"❌ 批量追加失败：{error_msg}")
            messagebox.showerror("错误", f"批量追加失败：{error_msg}")

    def deduplicate_chapters(self, chapters):
        """章节去重函数（基于内容哈希）"""
        seen_hashes = set()
        deduplicated = []
        for chapter in chapters:
            chapter_num, chapter_title, chapter_content, content_hash = chapter
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                deduplicated.append(chapter)
        return deduplicated

    def capture_full_page_content(self):
        """捕获当前页面的完整HTML源码，保存到本地文件"""
        if not self.driver:
            messagebox.showwarning("警告", "请先启动Edge浏览器！")
            return

        capture_thread = threading.Thread(target=self._capture_full_page_thread)
        capture_thread.daemon = True
        capture_thread.start()

    def _capture_full_page_thread(self):
        """完整页面捕获线程"""
        self.root.after(0, lambda: self.capture_full_page_btn.config(state='disabled', text='捕获中...'))
        self.log("📋 开始捕获完整页面内容...")

        try:
            # 等待页面完全加载
            self.log("⌛ 等待页面完全加载（包含动态内容）...")
            WebDriverWait(self.driver, 30).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(5)

            # 获取完整页面源码
            self.log("📥 获取完整HTML源码...")
            page_source = self.driver.page_source
            full_dom = self.driver.execute_script("return document.documentElement.outerHTML")
            if len(full_dom) > len(page_source):
                page_source = full_dom

            # 生成文件名
            page_title = self.driver.title.replace('/', '_').replace('\\', '_').replace(':', '').replace('*',
                                                                                                         '').replace(
                '?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
            if len(page_title) > 20:
                page_title = page_title[:20]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"完整页面内容_{page_title}_{timestamp}.html"
            save_path = os.path.join(os.getcwd(), filename)

            # 保存文件
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(page_source)

            self.log(f"✅ 完整页面内容已保存！")
            self.log(f"📁 保存路径：{save_path}")
            messagebox.showinfo("捕获成功", f"完整页面内容已保存！\n\n文件路径：{save_path}")

        except Exception as e:
            error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
            self.log(f"❌ 捕获完整页面失败：{error_msg}")
            messagebox.showerror("错误", f"捕获完整页面失败：{error_msg}")
        finally:
            self.root.after(0, lambda: self.capture_full_page_btn.config(state='normal', text='捕获完整页面内容'))

    def final_save(self):
        """最终整理保存：强制去重+按章节号排序（保留原标题序号，不额外添加）"""
        if not self.captured_chapters:
            messagebox.showwarning("警告", "没有捕获到任何章节内容！")
            return

        # 未选择保存路径则提示
        if not self.auto_save_enabled:
            self.select_save_path()
            if not self.auto_save_enabled:
                messagebox.showwarning("警告", "未选择保存路径，无法进行最终保存！")
                return

        # 步骤1：强制去重（核心修复）
        self.log("📋 开始最终整理保存：第一步→强制去重...")
        original_count = len(self.captured_chapters)
        deduplicated_chapters = self.deduplicate_chapters(self.captured_chapters)
        duplicate_count = original_count - len(deduplicated_chapters)

        if duplicate_count > 0:
            self.log(
                f"⚠️  去重完成：过滤了 {duplicate_count} 个重复章节（原{original_count}章→现{len(deduplicated_chapters)}章）")
            messagebox.showinfo("去重提示",
                                f"已自动过滤 {duplicate_count} 个重复章节\n当前有效章节数：{len(deduplicated_chapters)}")
        else:
            self.log(f"✅ 去重完成：无重复章节（共{len(deduplicated_chapters)}章）")

        # 步骤2：按章节号排序
        self.log("📋 第二步→按章节号排序...")
        sorted_chapters = sorted(deduplicated_chapters, key=lambda x: x[0])

        # 步骤3：整理格式并保存（核心修改：保留原标题序号，不额外添加）
        self.log("📋 第三步→优化格式并保存（保留原标题序号）...")
        full_novel = []
        # 添加小说信息头
        full_novel.append(f"📚 {self.novel_title}")
        full_novel.append(f"📅 捕获时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        full_novel.append(f"📖 总章节数：{len(sorted_chapters)}（已去重，保留原标题序号）")
        full_novel.append("=" * 80)
        full_novel.append("")

        # 拼接所有章节（直接使用原标题，保留自带序号，不额外添加）
        total_chars = 0
        for _, chapter_title, chapter_content, _ in sorted_chapters:
            formatted_chapter = [
                chapter_title,  # 核心修改：直接用原标题（已含序号），不再额外添加
                "=" * 80,
                chapter_content,  # 修复：将 content 改为 chapter_content（正确的变量名）
                ""  # 章节间空行分隔
            ]
            full_novel.append('\n'.join(formatted_chapter))
            total_chars += len(chapter_content)
            self.log(f"🔤 章节：{chapter_title}（{len(chapter_content)}字符）")

        # 保存文件（覆盖原有文件）
        try:
            with open(self.save_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(full_novel))

            success_msg = f"最终保存成功！\n文件路径：{self.save_path}\n小说标题：{self.novel_title}\n总章节数：{len(sorted_chapters)}（已去重）\n总字符数：{total_chars}\n✅ 格式优化完成，保留原标题序号，无重复章节"
            messagebox.showinfo("成功", success_msg)
            self.log(f"🎉 最终整理保存完成：{self.save_path}")
            self.log(success_msg)

            # 询问是否清空捕获记录
            if messagebox.askyesno("继续", "是否清空当前捕获记录，开始新的捕获任务？"):
                self.captured_chapters.clear()
                self.novel_title = "未知小说"
                self.auto_save_enabled = False
                self.save_path = None
                self.change_save_path_btn.config(state='disabled')
                self.log("已清空捕获记录，可开始新的捕获任务")

        except Exception as e:
            messagebox.showerror("错误", f"最终保存失败：{str(e)}")
            self.log(f"❌ 最终保存失败：{str(e)}")

    def log(self, message):
        """修复datetime使用错误的日志方法"""
        if self.progress_text is None:
            print(f"[日志] {message}")
            return
        # 修复：直接使用datetime.now()（因为已经通过from datetime import datetime导入）
        now = datetime.now().strftime("%H:%M:%S")
        self.progress_text.insert('end', f"[{now}] {message}\n")
        self.progress_text.see('end')

    def __del__(self):
        """程序退出时关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass


def main():
    print("=" * 80)
    print("          小说批量捕获工具 - 霜月短文专用版（自动追加保存+强去重）")
    print("=" * 80)
    print("核心功能：")
    print("📌 自动追加保存：捕获第一章时创建文件，后续章节自动追加")
    print("📌 三重去重机制：章节号+标题+内容哈希，彻底避免重复")
    print("📌 最终强制去重：整理时自动过滤重复章节，确保无冗余")
    print("📌 标题保留原序号：不额外添加序号，直接使用原标题（含序号）")
    print("📌 格式优化：自动按章节号排序，添加小说信息头")
    print("📌 精准解析：适配霜月短文《透视狂兵》页面结构")
    print("=" * 80)
    print("使用步骤：")
    print("1. 启动浏览器（自动/手动模式）")
    print("2. 登录霜月短文网站（通过Cookie自动登录）")
    print("3. 打开《透视狂兵》小说阅读页")
    print("4. 点击「捕获当前章节」（首次捕获会提示选择保存路径）")
    print("5. 切换章节重复步骤4，自动去重+追加保存")
    print("6. 捕获完成后点击「最终整理保存」（强制去重+排序，保留原标题序号）")
    print("=" * 80)

    # 检查依赖
    try:
        import win32api
    except ImportError:
        print("正在安装Windows系统依赖...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "--user"])

    root = Tk()
    app = NovelCaptureApp(root)
    root.mainloop()


if __name__ == "__main__":
    # 检查核心依赖
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.service import Service
        from selenium.webdriver.edge.options import Options
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
    except ImportError:
        print("正在安装必要依赖...")
        import subprocess

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "selenium", "webdriver-manager", "beautifulsoup4", "--user"])
        print("依赖安装完成，重启程序...")
        sys.exit()

    main()