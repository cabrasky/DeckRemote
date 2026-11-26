"""DeckRemote UI strings. To add a language: copy the "en" block, translate it and add the
Steam language name(s) to STEAM_LANGUAGES. Placeholders in {braces} must stay as they are."""
import os
import re

LANGUAGES = ["en", "es", "fr", "de", "it", "pt-BR", "pl", "ru", "tr", "ja", "ko", "zh-CN"]

# Steam's own language names (registry.vdf) -> our codes
STEAM_LANGUAGES = {"english": "en", "spanish": "es", "latam": "es", "french": "fr", "german": "de",
                   "italian": "it", "brazilian": "pt-BR", "portuguese": "pt-BR", "polish": "pl",
                   "russian": "ru", "turkish": "tr", "japanese": "ja", "koreana": "ko", "schinese": "zh-CN"}

S = {
    "en": dict(
        lang_name="English", choose_lang="Choose your language", lang_hint="Tap a language. You can change it later.",
        connected="Connected to PC", waiting="Waiting for PC…", off="Not sharing",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  bus {bus}",
        attach="On your PC, open USBip and attach\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="GENERIC · HID",
        rumble="Rumble", strong="Strong motor", weak="Weak motor", no_rumble="No rumble in generic mode",
        deck_buttons="Steam and ⋯ stay on your Deck", to_generic="Generic mode", to_xbox="Xbox 360 mode",
        quit="Disconnect & exit", pad_none="Open DeckRemote from Steam to use your controller",
        off_help="Couldn't start the virtual controller ({err})"),
    "es": dict(
        lang_name="Español", choose_lang="Elige tu idioma", lang_hint="Toca un idioma. Puedes cambiarlo luego.",
        connected="Conectado al PC", waiting="Esperando al PC…", off="Sin compartir",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  bus {bus}",
        attach="En el PC, abre USBip y conecta\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="GENÉRICO · HID",
        rumble="Vibración", strong="Motor fuerte", weak="Motor suave", no_rumble="Sin vibración en modo genérico",
        deck_buttons="Steam y ⋯ siguen en tu Deck", to_generic="Modo genérico", to_xbox="Modo Xbox 360",
        quit="Desconectar y salir", pad_none="Abre DeckRemote desde Steam para usar tu mando",
        off_help="No se pudo activar el mando virtual ({err})"),
    "fr": dict(
        lang_name="Français", choose_lang="Choisissez votre langue", lang_hint="Touchez une langue. Vous pourrez la changer plus tard.",
        connected="Connecté au PC", waiting="En attente du PC…", off="Pas de partage",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  bus {bus}",
        attach="Sur le PC, ouvrez USBip et connectez\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="GÉNÉRIQUE · HID",
        rumble="Vibration", strong="Moteur fort", weak="Moteur faible", no_rumble="Pas de vibration en mode générique",
        deck_buttons="Steam et ⋯ restent sur votre Deck", to_generic="Mode générique", to_xbox="Mode Xbox 360",
        quit="Déconnecter et quitter", pad_none="Lancez DeckRemote depuis Steam pour utiliser votre manette",
        off_help="Impossible de démarrer la manette virtuelle ({err})"),
    "de": dict(
        lang_name="Deutsch", choose_lang="Sprache wählen", lang_hint="Tippe auf eine Sprache. Du kannst sie später ändern.",
        connected="Mit dem PC verbunden", waiting="Warte auf den PC…", off="Nicht freigegeben",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  Bus {bus}",
        attach="Öffne auf dem PC USBip und verbinde\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="GENERISCH · HID",
        rumble="Vibration", strong="Starker Motor", weak="Schwacher Motor", no_rumble="Keine Vibration im generischen Modus",
        deck_buttons="Steam und ⋯ bleiben auf deinem Deck", to_generic="Generischer Modus", to_xbox="Xbox-360-Modus",
        quit="Trennen und beenden", pad_none="Starte DeckRemote über Steam, um deinen Controller zu nutzen",
        off_help="Virtueller Controller konnte nicht gestartet werden ({err})"),
    "it": dict(
        lang_name="Italiano", choose_lang="Scegli la lingua", lang_hint="Tocca una lingua. Potrai cambiarla in seguito.",
        connected="Connesso al PC", waiting="In attesa del PC…", off="Nessuna condivisione",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  bus {bus}",
        attach="Sul PC apri USBip e collega\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="GENERICO · HID",
        rumble="Vibrazione", strong="Motore forte", weak="Motore debole", no_rumble="Nessuna vibrazione in modalità generica",
        deck_buttons="Steam e ⋯ restano sul tuo Deck", to_generic="Modalità generica", to_xbox="Modalità Xbox 360",
        quit="Disconnetti ed esci", pad_none="Avvia DeckRemote da Steam per usare il controller",
        off_help="Impossibile avviare il controller virtuale ({err})"),
    "pt-BR": dict(
        lang_name="Português (BR)", choose_lang="Escolha seu idioma", lang_hint="Toque em um idioma. Você pode mudar depois.",
        connected="Conectado ao PC", waiting="Aguardando o PC…", off="Sem compartilhamento",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  barramento {bus}",
        attach="No PC, abra o USBip e conecte\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="GENÉRICO · HID",
        rumble="Vibração", strong="Motor forte", weak="Motor fraco", no_rumble="Sem vibração no modo genérico",
        deck_buttons="Steam e ⋯ continuam no seu Deck", to_generic="Modo genérico", to_xbox="Modo Xbox 360",
        quit="Desconectar e sair", pad_none="Abra o DeckRemote pela Steam para usar seu controle",
        off_help="Não foi possível iniciar o controle virtual ({err})"),
    "pl": dict(
        lang_name="Polski", choose_lang="Wybierz język", lang_hint="Dotknij języka. Możesz go później zmienić.",
        connected="Połączono z PC", waiting="Czekam na PC…", off="Brak udostępniania",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  magistrala {bus}",
        attach="Na PC otwórz USBip i podłącz\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="OGÓLNY · HID",
        rumble="Wibracje", strong="Silny silnik", weak="Słaby silnik", no_rumble="Brak wibracji w trybie ogólnym",
        deck_buttons="Steam i ⋯ zostają na Twoim Decku", to_generic="Tryb ogólny", to_xbox="Tryb Xbox 360",
        quit="Rozłącz i wyjdź", pad_none="Uruchom DeckRemote ze Steam, aby użyć kontrolera",
        off_help="Nie udało się uruchomić wirtualnego kontrolera ({err})"),
    "ru": dict(
        lang_name="Русский", choose_lang="Выберите язык", lang_hint="Нажмите на язык. Его можно сменить позже.",
        connected="Подключено к ПК", waiting="Ожидание ПК…", off="Доступ выключен",
        pc="ПК  {ip}", deck_info="Deck {ip}  ·  шина {bus}",
        attach="На ПК откройте USBip и подключите\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="ОБЫЧНЫЙ · HID",
        rumble="Вибрация", strong="Сильный мотор", weak="Слабый мотор", no_rumble="В обычном режиме нет вибрации",
        deck_buttons="Steam и ⋯ остаются на вашем Deck", to_generic="Обычный режим", to_xbox="Режим Xbox 360",
        quit="Отключить и выйти", pad_none="Запустите DeckRemote из Steam, чтобы использовать контроллер",
        off_help="Не удалось запустить виртуальный контроллер ({err})"),
    "tr": dict(
        lang_name="Türkçe", choose_lang="Dilinizi seçin", lang_hint="Bir dile dokunun. Daha sonra değiştirebilirsiniz.",
        connected="PC'ye bağlandı", waiting="PC bekleniyor…", off="Paylaşım yok",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  veri yolu {bus}",
        attach="PC'de USBip'i açın ve bağlayın\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="GENEL · HID",
        rumble="Titreşim", strong="Güçlü motor", weak="Zayıf motor", no_rumble="Genel modda titreşim yok",
        deck_buttons="Steam ve ⋯ Deck'inizde kalır", to_generic="Genel mod", to_xbox="Xbox 360 modu",
        quit="Bağlantıyı kes ve çık", pad_none="Kumandanızı kullanmak için DeckRemote'u Steam'den açın",
        off_help="Sanal kumanda başlatılamadı ({err})"),
    "ja": dict(
        lang_name="日本語", choose_lang="言語を選択", lang_hint="言語をタップしてください。あとで変更できます。",
        connected="PCに接続済み", waiting="PCを待っています…", off="共有していません",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  バス {bus}",
        attach="PCでUSBipを開いて接続:\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="汎用 · HID",
        rumble="振動", strong="強モーター", weak="弱モーター", no_rumble="汎用モードでは振動しません",
        deck_buttons="Steamと⋯ボタンはDeckに残ります", to_generic="汎用モード", to_xbox="Xbox 360モード",
        quit="切断して終了", pad_none="SteamからDeckRemoteを起動してください",
        off_help="仮想コントローラーを起動できませんでした ({err})"),
    "ko": dict(
        lang_name="한국어", choose_lang="언어 선택", lang_hint="언어를 탭하세요. 나중에 바꿀 수 있습니다.",
        connected="PC에 연결됨", waiting="PC를 기다리는 중…", off="공유 안 함",
        pc="PC  {ip}", deck_info="Deck {ip}  ·  버스 {bus}",
        attach="PC에서 USBip을 열고 연결하세요\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="일반 · HID",
        rumble="진동", strong="강한 모터", weak="약한 모터", no_rumble="일반 모드에서는 진동이 없습니다",
        deck_buttons="Steam과 ⋯ 버튼은 Deck에 남아 있습니다", to_generic="일반 모드", to_xbox="Xbox 360 모드",
        quit="연결 해제 후 종료", pad_none="Steam에서 DeckRemote를 실행하세요",
        off_help="가상 컨트롤러를 시작할 수 없습니다 ({err})"),
    "zh-CN": dict(
        lang_name="简体中文", choose_lang="选择语言", lang_hint="点按一种语言，之后可以更改。",
        connected="已连接到电脑", waiting="正在等待电脑…", off="未共享",
        pc="电脑  {ip}", deck_info="Deck {ip}  ·  总线 {bus}",
        attach="在电脑上打开 USBip 并连接\n{ip}  →  {bus}",
        chip_xbox="XBOX 360 · XINPUT", chip_generic="通用 · HID",
        rumble="振动", strong="强电机", weak="弱电机", no_rumble="通用模式下没有振动",
        deck_buttons="Steam 和 ⋯ 键仍由 Deck 使用", to_generic="通用模式", to_xbox="Xbox 360 模式",
        quit="断开并退出", pad_none="请从 Steam 启动 DeckRemote 以使用手柄",
        off_help="无法启动虚拟手柄（{err}）"),
}


def steam_language():
    """Our code for the language set in Steam, or None."""
    for path in ("~/.steam/registry.vdf", "~/.local/share/Steam/registry.vdf"):
        try:
            with open(os.path.expanduser(path), encoding="utf-8", errors="ignore") as f:
                m = re.search(r'"language"\s+"([a-z]+)"', f.read())
            if m:
                return STEAM_LANGUAGES.get(m.group(1))
        except OSError:
            continue
    return None


def text(lang, key, **kw):
    table = S.get(lang) or S["en"]
    return (table.get(key) or S["en"][key]).format(**kw)
