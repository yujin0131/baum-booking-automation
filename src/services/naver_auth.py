import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from loguru import logger
import pyotp


class NaverAuth:
    NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"

    def __init__(self, headless: bool = False, otp_secret: Optional[str] = None):
        self.headless = headless
        self.otp_secret = otp_secret
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def _random_delay(self, min_ms: int = 50, max_ms: int = 150):
        delay = random.uniform(min_ms / 1000, max_ms / 1000)
        await asyncio.sleep(delay)

    async def _random_type(self, page: Page, selector: str, text: str):
        element = await page.wait_for_selector(selector, state="visible")
        await element.click()
        await self._random_delay(100, 300)

        for char in text:
            await page.keyboard.type(char)
            await self._random_delay(50, 200)

    async def _move_mouse(self, page: Page, x: int, y: int):
        current_pos = await page.evaluate("() => ({x: 0, y: 0})")

        steps = random.randint(5, 15)
        for i in range(steps):
            progress = (i + 1) / steps

            noise_x = random.uniform(-5, 5)
            noise_y = random.uniform(-5, 5)

            next_x = current_pos['x'] + (x - current_pos['x']) * progress + noise_x
            next_y = current_pos['y'] + (y - current_pos['y']) * progress + noise_y

            await page.mouse.move(next_x, next_y)
            await self._random_delay(10, 30)

    async def _random_mouse_movement(self, page: Page):
        viewport = page.viewport_size
        if viewport:
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, viewport['width'] - 100)
                y = random.randint(100, viewport['height'] - 100)
                await self._move_mouse(page, x, y)
                await self._random_delay(100, 300)

    async def _scroll_randomly(self, page: Page):
        scroll_amount = random.randint(50, 200)
        await page.mouse.wheel(0, scroll_amount)
        await self._random_delay(200, 500)
        await page.mouse.wheel(0, -scroll_amount)
        await self._random_delay(100, 200)

    async def _handle_2step_auth(self):
        """2단계 인증 처리 (OTP 자동 입력)"""
        if not self.otp_secret:
            logger.warning("OTP 비밀키 없음. 수동 처리 필요")
            await self.page.wait_for_url("**/naver.com/**", timeout=120000)
            return

        try:
            # "OTP로 로그인" 버튼 찾기 및 클릭
            otp_btn = await self.page.query_selector("text=OTP")
            if not otp_btn:
                otp_btn = await self.page.query_selector("text=일회용")
            if otp_btn:
                await otp_btn.click()
                await self._random_delay(1000, 2000)

            # OTP 코드 생성
            totp = pyotp.TOTP(self.otp_secret)
            otp_code = totp.now()
            logger.info(f"OTP 코드 생성: {otp_code}")

            # OTP 입력창 찾기
            otp_input = await self.page.wait_for_selector(
                "input[type='text'], input[type='number'], input[placeholder*='인증'], input[name*='otp']",
                timeout=10000
            )

            if otp_input:
                # OTP 코드 입력
                await otp_input.click()
                await self._random_delay(200, 400)
                await self.page.evaluate(f'''
                    document.querySelector("input[type='text'], input[type='number']").value = "{otp_code}";
                ''')
                await self._random_delay(300, 500)

                # 확인 버튼 클릭
                confirm_btn = await self.page.query_selector("button[type='submit'], .btn_confirm, text=확인")
                if confirm_btn:
                    await confirm_btn.click()
                    await self._random_delay(2000, 3000)

                logger.info("OTP 인증 완료")
            else:
                logger.warning("OTP 입력창을 찾을 수 없음")

        except Exception as e:
            logger.error(f"2단계 인증 처리 중 오류: {e}")
            logger.warning("수동 처리 대기...")
            await self.page.wait_for_url("**/naver.com/**", timeout=120000)

    async def init_browser(self) -> Page:
        self._playwright = await async_playwright().start()

        # Chromium
        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-breakpad',
                '--disable-component-extensions-with-background-pages',
                '--disable-extensions',
                '--disable-sync',
                '--disable-translate',
                '--disable-default-apps',
                '--no-default-browser-check',
                '--no-first-run',
                '--no-pings',
                '--password-store=basic',
                '--use-mock-keychain',
                '--ignore-certificate-errors',
                '--ignore-certificate-errors-spki-list',
                '--window-size=1920,1080',
                '--start-maximized',
            ],
        )

        # 컨텍스트 생성
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            extra_http_headers={
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            },
        )

        # 불필요한 리소스 차단으로 메모리/CPU 최적화 (stylesheet는 제외 - 렌더링에 필요할 수 있음)
        await self.context.route("**/*", lambda route: (
            route.abort() if route.request.resource_type in ["image", "media", "font"]
            else route.continue_()
        ))

        # 완벽한 봇 탐지 우회 스크립트
        await self.context.add_init_script("""
            // 1. WebDriver 속성 완전 제거
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            delete navigator.__proto__.webdriver;

            // 2. Chrome 객체 완전 구현
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {
                    isInstalled: false,
                    InstallState: {
                        DISABLED: 'disabled',
                        INSTALLED: 'installed',
                        NOT_INSTALLED: 'not_installed'
                    },
                    RunningState: {
                        CANNOT_RUN: 'cannot_run',
                        READY_TO_RUN: 'ready_to_run',
                        RUNNING: 'running'
                    }
                }
            };

            // 3. Permissions API 완전 우회
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // 4. Plugins 고급 위장
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: ""},
                            description: "",
                            filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                            length: 1,
                            name: "Chrome PDF Viewer"
                        },
                        {
                            0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
                            1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable"},
                            description: "Native Client",
                            filename: "internal-nacl-plugin",
                            length: 2,
                            name: "Native Client"
                        }
                    ];
                    plugins.refresh = function() {};
                    plugins.item = function(index) { return this[index] || null; };
                    plugins.namedItem = function(name) {
                        return this.find(p => p.name === name) || null;
                    };
                    return plugins;
                }
            });

            // 5. MimeTypes 위장
            Object.defineProperty(navigator, 'mimeTypes', {
                get: () => {
                    const mimeTypes = [
                        {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: {}},
                        {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: {}},
                        {type: "application/x-nacl", suffixes: "", description: "Native Client Executable", enabledPlugin: {}},
                        {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: {}}
                    ];
                    mimeTypes.item = function(index) { return this[index] || null; };
                    mimeTypes.namedItem = function(name) {
                        return this.find(m => m.type === name) || null;
                    };
                    return mimeTypes;
                }
            });

            // 6. Languages 설정
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en']
            });

            // 7. Platform & Hardware 정보
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });

            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });

            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });

            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.'
            });

            // 8. Connection API
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    downlink: 10,
                    effectiveType: '4g',
                    rtt: 50,
                    saveData: false
                })
            });

            // 9. Battery API 우회
            if (navigator.getBattery) {
                const originalGetBattery = navigator.getBattery;
                navigator.getBattery = function() {
                    return originalGetBattery.apply(this, arguments).then(battery => {
                        Object.defineProperty(battery, 'charging', { get: () => true });
                        Object.defineProperty(battery, 'chargingTime', { get: () => 0 });
                        Object.defineProperty(battery, 'dischargingTime', { get: () => Infinity });
                        Object.defineProperty(battery, 'level', { get: () => 1 });
                        return battery;
                    });
                };
            }

            // 10. Geolocation API
            if (navigator.geolocation) {
                const originalGetCurrentPosition = navigator.geolocation.getCurrentPosition;
                navigator.geolocation.getCurrentPosition = function(success, error, options) {
                    const position = {
                        coords: {
                            accuracy: 20,
                            altitude: null,
                            altitudeAccuracy: null,
                            heading: null,
                            latitude: 37.5665,
                            longitude: 126.9780,
                            speed: null
                        },
                        timestamp: Date.now()
                    };
                    success(position);
                };
            }

            // 11. Screen 정보 정교화
            Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
            Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });

            // 12. Notification API
            Object.defineProperty(Notification, 'permission', {
                get: () => 'default'
            });

            // 13. toString() 오버라이드로 네이티브 함수처럼 보이게
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === navigator.permissions.query) {
                    return 'function query() { [native code] }';
                }
                if (this === navigator.getBattery) {
                    return 'function getBattery() { [native code] }';
                }
                return originalToString.call(this);
            };

            // 14. Canvas Fingerprinting 노이즈 추가
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function() {
                const imageData = originalGetImageData.apply(this, arguments);
                // 미세한 노이즈 추가
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] = imageData.data[i] + Math.floor(Math.random() * 3) - 1;
                }
                return imageData;
            };

            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    // 미세한 변경
                    for (let i = 0; i < Math.min(10, imageData.data.length); i += 4) {
                        imageData.data[i] = imageData.data[i] + 1;
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };

            // 15. WebGL Fingerprinting 우회
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) { // UNMASKED_VENDOR_WEBGL
                    return 'Intel Inc.';
                }
                if (parameter === 37446) { // UNMASKED_RENDERER_WEBGL
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.apply(this, arguments);
            };

            // 16. AudioContext Fingerprinting 우회
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
                AudioContext.prototype.createAnalyser = function() {
                    const analyser = originalCreateAnalyser.apply(this, arguments);
                    const originalGetFloatFrequencyData = analyser.getFloatFrequencyData;
                    analyser.getFloatFrequencyData = function(array) {
                        originalGetFloatFrequencyData.apply(this, arguments);
                        for (let i = 0; i < array.length; i++) {
                            array[i] = array[i] + Math.random() * 0.0001;
                        }
                    };
                    return analyser;
                };
            }

            // 17. iframe contentWindow 우회
            const originalContentWindow = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function() {
                    const win = originalContentWindow.get.call(this);
                    if (win) {
                        try {
                            win.navigator.webdriver = undefined;
                        } catch(e) {}
                    }
                    return win;
                }
            });

            // 18. Error Stack Trace 정리
            Error.stackTraceLimit = 10;

            // 19. Date/Timezone 일관성
            Date.prototype.getTimezoneOffset = function() {
                return -540; // KST (UTC+9)
            };

            // 20. MediaDevices 우회
            if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
                const originalEnumerateDevices = navigator.mediaDevices.enumerateDevices;
                navigator.mediaDevices.enumerateDevices = function() {
                    return originalEnumerateDevices.apply(this, arguments).then(devices => {
                        return devices.map((device, index) => ({
                            deviceId: device.deviceId || `default${index}`,
                            groupId: device.groupId || `group${index}`,
                            kind: device.kind,
                            label: device.label || ''
                        }));
                    });
                };
            }

            console.log('Advanced stealth mode activated');
        """)

        self.page = await self.context.new_page()

        logger.info("브라우저 초기화 완료")
        return self.page

    async def login(self, username: str, password: str) -> bool:

        if not self.page:
            await self.init_browser()

        try:
            logger.info(f"로그인 페이지 이동 중: {self.NAVER_LOGIN_URL}")
            await self.page.goto(self.NAVER_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            await self._random_delay(1000, 2000)
            logger.info("로그인 페이지 로드 완료")
            await self._random_mouse_movement(self.page)

            # JavaScript로 직접 값 설정 (봇 탐지 우회)
            await self.page.evaluate(f'''
                document.querySelector("#id").value = "{username}";
                document.querySelector("#id").dispatchEvent(new Event("input", {{ bubbles: true }}));
            ''')
            await self._random_delay(300, 600)

            await self.page.evaluate(f'''
                document.querySelector("#pw").value = "{password}";
                document.querySelector("#pw").dispatchEvent(new Event("input", {{ bubbles: true }}));
            ''')
            await self._random_delay(500, 1000)

            login_btn = await self.page.wait_for_selector(".btn_login", state="visible")

            box = await login_btn.bounding_box()
            if box:
                center_x = box['x'] + box['width'] / 2
                center_y = box['y'] + box['height'] / 2
                await self._move_mouse(self.page, int(center_x), int(center_y))
                await self._random_delay(100, 200)

            await login_btn.click()
            await self._random_delay(2000, 3000)
            current_url = self.page.url

            # CAPTCHA 뜨는경우
            if "captcha" in current_url.lower():
                logger.warning("CAPTCHA. 관리자 확인 필요")
                await self.page.wait_for_url("**/naver.com/**", timeout=120000)

            # 2단계 인증 처리
            if "2step" in current_url or "otp" in current_url.lower():
                logger.info("2단계 인증 감지")
                await self._handle_2step_auth()

            if "nid.naver.com" not in self.page.url or "login" not in self.page.url.lower():
                logger.success("로그인 성공")
                return True
            else:
                error_msg = await self.page.query_selector(".error_message, .err_common")
                if error_msg:
                    error_text = await error_msg.text_content()
                    logger.error(f"{error_text}")
                else:
                    logger.error("로그인 실패: 알 수 없는 오류")
                return False

        except Exception as e:
            logger.error(f"로그인 중 오류 발생: {e}")
            return False

    async def get_cookies(self) -> list:
        if self.context:
            return await self.context.cookies()
        return []

    async def save_session(self, filepath: str):
        if self.context:
            import tempfile
            import shutil
            from pathlib import Path

            try:
                # 임시 파일에 먼저 저장
                dir_path = Path(filepath).parent or Path(".")
                with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, suffix='.tmp', delete=False) as tmp:
                    tmp_path = tmp.name

                await self.context.storage_state(path=tmp_path)

                # atomic rename으로 원본 파일 교체
                shutil.move(tmp_path, filepath)
                logger.info(f"세션이 {filepath}에 저장되었습니다.")
            except Exception as e:
                logger.error(f"세션 저장 실패: {e}")
                # 임시 파일 정리
                try:
                    if 'tmp_path' in locals():
                        Path(tmp_path).unlink(missing_ok=True)
                except:
                    pass

    async def load_session(self, filepath: str) -> bool:
        import asyncio
        from pathlib import Path

        session_path = Path(filepath)
        if not session_path.exists():
            logger.warning(f"세션 파일이 존재하지 않음: {filepath}")
            return False

        # 파일 접근 가능할 때까지 재시도 (최대 3회)
        for attempt in range(3):
            try:
                # 파일 읽기 테스트
                with open(filepath, 'r') as f:
                    f.read(1)
                break
            except OSError as e:
                if e.errno == 16:  # Device or resource busy
                    logger.warning(f"세션 파일 잠금 감지, 재시도 {attempt + 1}/3")
                    await asyncio.sleep(1)
                    if attempt == 2:
                        logger.error("세션 파일 접근 불가, 파일 초기화 후 재로그인 필요")
                        try:
                            session_path.write_text("{}")
                        except OSError:
                            pass
                        return False
                else:
                    raise

        try:
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-extensions',
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--disable-translate',
                    '--metrics-recording-only',
                    '--mute-audio',
                    '--no-first-run',
                    '--safebrowsing-disable-auto-update',
                    '--disable-blink-features=AutomationControlled',
                    '--js-flags=--max-old-space-size=128',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-component-update',
                    '--disable-breakpad',
                    '--disable-hang-monitor',
                    '--single-process',
                    '--no-zygote',
                ],
            )
            self.context = await self.browser.new_context(
                storage_state=filepath,
                viewport={'width': 1280, 'height': 720},
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                locale='ko-KR',
                timezone_id='Asia/Seoul',
            )

            # 불필요한 리소스 차단으로 메모리/CPU 최적화 (stylesheet는 제외)
            await self.context.route("**/*", lambda route: (
                route.abort() if route.request.resource_type in ["image", "media", "font"]
                else route.continue_()
            ))

            self.page = await self.context.new_page()
            logger.info(f"세션이 {filepath}에서 로드되었습니다.")
            return True
        except Exception as e:
            logger.error(f"세션 로드 실패: {e}")
            return False

    async def is_logged_in(self) -> bool:
        if not self.page:
            return False

        try:
            await self.page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=60000)
            await self._random_delay(1000, 2000)
            login_area = await self.page.query_selector(".MyView-module__link_login___HpHMW")
            return login_area is None
        except Exception:
            return False

    async def close(self):
        if self.browser:
            await self.browser.close()
        if hasattr(self, '_playwright') and self._playwright:
            await self._playwright.stop()
        logger.info("브라우저가 종료되었습니다.")
