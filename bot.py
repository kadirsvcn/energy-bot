import argparse
import ctypes
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
from PIL import ImageGrab

# Odaklanılacak pencere başlığı (önce tam eşleşme, bulunamazsa içinde geçen aranır)
PENCERE_ADI = "METIN2"

# NPC isimlerinin yazıldığı yeşil ton ve kanal başına tolerans
ISIM_RENGI = (122, 231, 93)
RENK_TOLERANSI = 45

# Eşleşen ismin merkezine göre tıklama kayması (isim NPC'nin tepesinde durur)
TIK_KAYDIRMA = (0, 120)

# Şablon eşleşmesi bu değerin altındaysa "bulunamadı" sayılır (0-1)
ESIK = 0.6

# "Marketi aç" düğmesi için eşleşme eşiği (arayüz görüntüsü olduğu için daha yüksek)
MARKET_ESIGI = 0.8
DUKKAN_KAPAT_ESIGI = 0.8
DUKKAN_KAPAT_OFSET = (162, 11)

# Market açıldıktan sonra sağ tıklanacak eşya (hancer.png) için eşleşme eşiği
ESYA_ESIGI = 0.8

# Yeni alınan eşyalar envanterde parlar (new-hancer.png); üstünden geçilince söner.
# Tek tek aramak yerine envanterin bütün hücreleri hızlıca taranıyor.
YENI_ESYA_ESIGI = 0.8
HUCRE_BEKLEME = 0.04       # her hücrenin üstünde ne kadar durulacak
IZGARA_TUR_SINIRI = 3      # parlayan kalırsa tarama kaç kez tekrarlanacak

# Envanter ızgarası: başlık çubuğunun sol üst köşesine göre ilk hücrenin merkezi,
# hücreler arası adım ve ızgara boyutu (ölçülerek bulundu)
IZGARA_ILK_HUCRE = (6, 63)
IZGARA_ADIMI = 32
IZGARA_SUTUN = 5
IZGARA_SATIR = 9

# Market penceresinin açılması ve eşyanın görünmesi için beklenecek süre (saniye)
ESYA_ARAMA_SURESI = 5.0

# Bir görüntü çıkana kadar beklerken taramalar arası süre. Her tarama zaten
# ekran görüntüsü + şablon eşleştirme demek (~40 ms), o yüzden kısa tutulabilir:
# beklemenin tamamı, aranan pencere çıktıktan sonra boşa geçen süredir.
ARAMA_ARALIGI = 0.06

TUS_ARASI = 0.16
TUS_BASILI_KALMA = 0.05  # tuşun basılı tutulma süresi (oyunun algılaması için)

# 1. envanter sekmesini arayıp tıklama adımı (kapalıyken sadece ESC + "ı" gönderilir)
ENVANTER_SEKMESI_TIKLA = True

# 1. sekme, şablonla aranmıyor: sekmeler birbirine çok benziyor (komşusuna 0.84'e
# kadar benzeyebiliyor) ve pencereler yarı saydam olduğu için skorlar arka plana
# göre oynuyor. Konumu başlık çubuğunun sol üst köşesine göre hesaplıyoruz.
SEKME1_OFSET = (11, 34)   # başlık sol üst köşesine göre 1. sekmenin merkezi
SEKME_ADIMI = 39          # sekmeler arası yatay mesafe (I, II, III, IV)
SEKME_BOLGESI = (36, 18)  # sekmenin yaklaşık boyutu (değişim kontrolü için)
SEKMELER = (1,)         # sırayla gezilecek envanter sekmeleri (ilkine tıklanmaz)
ENVANTER_ARAMA_SURESI = 5.0

# Envanter penceresi açılana kadar "ı" tuşuna basma.
# Başlık, yarı saydam arka plandan etkilenmesin diye yalnızca yazı pikselleri
# üzerinden aranıyor; bu eşiğin üstündeki gri değerler "yazı" sayılır.
YAZI_ESIGI = 180
ENVANTER_PENCERE_ESIGI = 0.8


# Sekme geçmediyse kaç kez daha tıklanacak ve tıklamadan sonra ne kadar beklenecek
ENVANTER_DENEMESI = 3
SEKME_KONTROL_BEKLEME = 0.4

# Seçili sekmenin görüntüsü değişir ama şablon eşleşmesi yüksek kalabilir; bu
# yüzden geçiş, sekme bölgesindeki ortalama piksel değişiminden anlaşılıyor.
SEKME_DEGISIM_ESIGI = 3.0

# Yükseltme döngüsü: çekiç -> hançer -> Evet, hançer bitene kadar
HAMMER_ESIGI = 0.8
EVET_ESIGI = 0.8
EVET_ARAMA_SURESI = 5.0
EVET_TIK_KAYDIRMA = (8, 4)   # düğmenin merkezine göre sağa/aşağı kayma (piksel)
EVET_YERLESME_BEKLEME = 0.15  # onay penceresi çizildikten sonra tıklamadan önce
EVET_DENEMESI = 3            # düğme kaybolmadıysa kaç kez daha tıklanacak
# Tıklamadan sonra "pencere kapandı mı" kontrolü: önce kısa bir oturma payı,
# sonra kapanana kadar tekrar tekrar bakılır. Kapanır kapanmaz devam edilir;
# süre dolarsa tıklama işlememiş sayılıp tekrarlanır.
EVET_KONTROL_ILK_BEKLEME = 0.08
EVET_KONTROL_BEKLEME = 0.6
ADIM_BEKLEME = 0.15       # çekiç ve hançer tıklamaları arası
YUKSELTME_BEKLEME = 0.45  # Evet'ten sonra sonucun oluşması için
MAKS_YUKSELTME = 200      # tıklamalar işlemezse sonsuz döngüye girmemek için üst sınır
TUR_HATA_SINIRI = 3       # arka arkaya kaç tur başarısız olursa durulacak

# NPC'ye tıkladıktan sonra menünün açılması için beklenen süre (saniye).
# Menü geç açılırsa sorun değil: "Marketi aç" düğmesi zaten çıkana kadar
# aranıyor (ESYA_ARAMA_SURESI), bu yüzden burada beklemek şart değil.
MENU_BEKLEME = 0.5

# NPC, market düğmesi ve envanterdeki eşyalar tek sol tık alır.
# Bu sayı yalnızca envanter sekmesi için kullanılıyor.
TIK_SAYISI = 2
TIK_ARASI = 0.1

# Oyun arayüzü imleci kendi takip ettiği için önce taşıyıp bekliyoruz, sonra
# basıp bırakıyoruz; anlık bas-bırak olaylarını arayüz kaçırabiliyor.
FARE_TASIMA_BEKLEME = 0.09
TIK_BASILI_KALMA = 0.05

# İmleç hedefe ışınlanmaz, küçük adımlarla kaydırılır (gerçek fare gibi)
KAYDIRMA_ADIMI = 20        # her adımda en fazla kaç piksel
KAYDIRMA_BEKLEME = 0.008   # adımlar arası bekleme (saniye)
KAYDIRMA_MAKS_ADIM = 400   # sonsuz döngüye karşı üst sınır
# Uzak hedeflerde yolun tamamı adım adım gidilmez: oyunun gerçek harekete
# ihtiyacı hedefin yakınında, uzaktaki düz yol boşa zaman. İmleç önce hedefin
# bu kadar yakınına ışınlanır, kalan mesafe adım adım kapatılır. 0 = kapalı
# (tüm yol adımlanır, eski davranış).
KAYDIRMA_YAKIN_MESAFE = 110

# Tıklama yöntemi: "sendinput" (gerçek fare olayı) veya "mesaj" (pencereye
# doğrudan Windows mesajı). Arayüz düğmeleri birinde çalışmazsa diğerini dene.
TIK_YONTEMI = "sendinput"
AKTIF_PENCERE = None  # odak kontrolü ve mesaj yöntemi için gereken pencere

# Oyun tekrar öne alındıktan sonra girdi göndermeden önce beklenecek süre
ODAK_SONRASI_BEKLEME = 0.2

# Eşyaya kaç sağ tık ve tıklar arası bekleme (saniye)
SAG_TIK_SAYISI = 5
SAG_TIK_ARASI = 0.7

# Market düğmesi çıkmadıysa NPC tıklaması bulunana kadar tekrarlanır;
# denemeler arası bu kadar beklenir (saniye)
DENEME_ARASI = 0.3

# --loop modunda turlar arası bekleme (saniye)
BEKLEME = 1.2

SABLON_DOSYASI = Path(__file__).with_name("sablon_npc.png")
MARKET_DOSYASI = Path(__file__).with_name("open-market.png")
DUKKAN_KAPAT_DOSYASI = Path(__file__).with_name("dukkan-close.png")
ESYA_DOSYASI = Path(__file__).with_name("hancer.png")
YENI_ESYA_DOSYASI = Path(__file__).with_name("new-hancer.png")
ENVANTER_DOSYASI = Path(__file__).with_name("envanter1.png")
# Envanterin açık olduğunu başlık çubuğundan anlıyoruz: sekme şeridi (envanter.png)
# hangi sekmenin seçili olduğuna göre değiştiği için güvenilir değil.
ENVANTER_PENCERE_DOSYASI = Path(__file__).with_name("envanter_baslik.png")
HAMMER_DOSYASI = Path(__file__).with_name("hammer.png")
EVET_DOSYASI = Path(__file__).with_name("evet.png")

# Fare sol üst köşeye giderse programı durdur
pyautogui.FAILSAFE = True

# Arayüzdeki "Kapat" düğmesi bunu kurar; döngüler her adımda buna bakar.
DURDURMA_BAYRAGI = threading.Event()
# Arayüzdeki "Duraklat" düğmesi bunu kurar; bot kaldığı yerde bekler.
DURAKLATMA_BAYRAGI = threading.Event()
DURAKLAMA_YOKLAMA = 0.1  # duraklamadan çıkıldı mı diye bakma aralığı (saniye)


def durduruldu():
    """Bu adımda çıkılmalı mı? Duraklatıldıysa ÖNCE burada bekler.

    Döngüler zaten her adımda buna bakıyor; duraklatma da bu yüzden buraya
    kondu: her kontrol noktası aynı zamanda güvenli bir duraklama noktası
    oluyor ve bot bir tıklama dizisinin ortasında donup kalmıyor.
    """
    duraklamayi_bekle()
    return DURDURMA_BAYRAGI.is_set()


def durdurma_istendi():
    """Durdurma bayrağını beklemeden okur (arayüz iş parçacığı için)."""
    return DURDURMA_BAYRAGI.is_set()


def duraklamayi_bekle():
    """Duraklatıldıysa 'devam' ya da 'kapat' gelene kadar bekler.

    Beklerken hiçbir girdi gönderilmediği için fare ve klavye kullanıcıda
    kalır; devam edilince bot kaldığı adımdan sürer. Duraklamada geçen
    saniyeyi döner: süre sınırlı aramalar bu kadar uzatılır, yoksa duraklama
    boyunca zaman aşımına uğrarlardı.
    """
    if not DURAKLATMA_BAYRAGI.is_set() or DURDURMA_BAYRAGI.is_set():
        return 0.0
    print("\n|| Duraklatıldı - 'Devam et' bekleniyor (fare serbest).")
    basladi = time.time()
    while DURAKLATMA_BAYRAGI.is_set() and not DURDURMA_BAYRAGI.is_set():
        time.sleep(DURAKLAMA_YOKLAMA)
    print("|| Kapatılıyor." if DURDURMA_BAYRAGI.is_set() else "|| Devam ediliyor.\n")
    return time.time() - basladi


def durdur():
    """Botu tamamen durdurur (duraklamış olsa bile beklemeden çıkar)."""
    DURDURMA_BAYRAGI.set()
    DURAKLATMA_BAYRAGI.clear()


def durdurmayi_sifirla():
    DURDURMA_BAYRAGI.clear()
    DURAKLATMA_BAYRAGI.clear()


def duraklat():
    DURAKLATMA_BAYRAGI.set()


def devam_et():
    DURAKLATMA_BAYRAGI.clear()


def duraklatildi():
    return DURAKLATMA_BAYRAGI.is_set()

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
SW_RESTORE = 9
# Sanal masaüstü (tüm ekranların kapladığı dikdörtgen) ölçüleri
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_INTEGRITY_LEVEL = 25
BUTUNLUK_ORTA = 0x2000
BUTUNLUK_YUKSEK = 0x3000
VK_MENU = 0x12  # ALT tuşu
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1
INPUT_MOUSE = 0

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000  # mutlak konum TÜM ekranlara göre ölçeklensin
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

FARE_BAYRAKLARI = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
}

# Pencereye doğrudan mesaj göndererek tıklama (arayüz düğmeleri için alternatif)
WM_MOUSEMOVE = 0x0200
FARE_MESAJLARI = {
    "left": (0x0201, 0x0202, 0x0001),   # DOWN, UP, MK_LBUTTON
    "right": (0x0204, 0x0205, 0x0002),  # DOWN, UP, MK_RBUTTON
}

# Oyun tuşları klavye düzenine göre değil FİZİKSEL tuşa (tarama kodu) göre okur;
# bu yüzden tuşlar sanal kodla değil tarama koduyla gönderiliyor.
TARAMA_KODLARI = {

    "ı": 0x17,     # Türkçe Q klavyede "ı" (US klavyede I tuşunun yeri)
    "i": 0x27,     # Türkçe Q klavyede "i" (US klavyede ; tuşunun yeri)
    "enter": 0x1C,
}


# --------------------------------------------------------------------------
# Ekranlar (monitörler)
# --------------------------------------------------------------------------

class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                                      ctypes.POINTER(wintypes.RECT), ctypes.c_double)
MONITORINFOF_PRIMARY = 0x1


def sanal_ekran():
    """Tüm ekranların kapladığı dikdörtgen: (sol, ust, genislik, yukseklik).

    İkinci ekran birincinin sağındaysa sol=0 genislik=3840 gibi; solundaysa
    sol negatif olur. Fare ve ekran görüntüsü hesapları buna göre yapılır.
    """
    return (user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))


def ekranlar():
    """Bağlı ekranları soldan sağa sıralı liste olarak döner.

    Her öğe: {"no": 1'den başlayan sıra, "sol", "ust", "genislik",
    "yukseklik", "birincil"}.
    """
    bulunan = []

    def _topla(tutamac, _hdc, _rect, _veri):
        bilgi = _MONITORINFO()
        bilgi.cbSize = ctypes.sizeof(_MONITORINFO)
        if user32.GetMonitorInfoW(tutamac, ctypes.byref(bilgi)):
            r = bilgi.rcMonitor
            bulunan.append({"sol": r.left, "ust": r.top,
                            "genislik": r.right - r.left,
                            "yukseklik": r.bottom - r.top,
                            "birincil": bool(bilgi.dwFlags & MONITORINFOF_PRIMARY)})
        return 1

    user32.EnumDisplayMonitors(0, 0, _MONITORENUMPROC(_topla), 0)
    bulunan.sort(key=lambda e: (e["sol"], e["ust"]))
    for sira, ekran in enumerate(bulunan, start=1):
        ekran["no"] = sira
    return bulunan


def ekran_etiketi(ekran):
    """Arayüzde ve kayıtta gösterilecek kısa ekran tanımı."""
    return (f"Ekran {ekran['no']} - {ekran['genislik']}x{ekran['yukseklik']} "
            f"@({ekran['sol']},{ekran['ust']})" + (" (birincil)" if ekran["birincil"] else ""))


def ekranlari_listele():
    print("Bağlı ekranlar:")
    for ekran in ekranlar():
        print(f"  - {ekran_etiketi(ekran)}")


def ekranda_mi(pencere, ekran):
    """Pencerenin MERKEZİ bu ekranın içindeyse True.

    Merkeze bakıyoruz: pencere iki ekrana taşmışsa hangi ekranda 'durduğu'
    kenarlarına değil ortasına göre belirlensin.
    """
    mx = pencere.left + pencere.width // 2
    my = pencere.top + pencere.height // 2
    return (ekran["sol"] <= mx < ekran["sol"] + ekran["genislik"]
            and ekran["ust"] <= my < ekran["ust"] + ekran["yukseklik"])


def pencerenin_ekrani(pencere):
    """Pencerenin bulunduğu ekranı döner, hiçbirine denk gelmiyorsa None."""
    for ekran in ekranlar():
        if ekranda_mi(pencere, ekran):
            return ekran
    return None


# --------------------------------------------------------------------------
# Pencere işleri
# --------------------------------------------------------------------------

def yonetici_mi():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def pencere_butunluk_seviyesi(pencere):
    """Pencerenin sahibi sürecin bütünlük (integrity) seviyesini döner, bilinmiyorsa None.

    0x2000 = orta (normal program), 0x3000 = yüksek (yönetici).
    """
    advapi32 = ctypes.windll.advapi32
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(pencere._hWnd, ctypes.byref(pid))
    surec = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not surec:
        return None
    try:
        jeton = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(surec, TOKEN_QUERY, ctypes.byref(jeton)):
            return None
        boyut = wintypes.DWORD()
        advapi32.GetTokenInformation(jeton, TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(boyut))
        tampon = ctypes.create_string_buffer(boyut.value)
        if not advapi32.GetTokenInformation(jeton, TOKEN_INTEGRITY_LEVEL, tampon,
                                            boyut, ctypes.byref(boyut)):
            return None
        sid = ctypes.c_void_p(ctypes.cast(tampon, ctypes.POINTER(ctypes.c_void_p))[0])
        advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
        advapi32.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
        adet = advapi32.GetSidSubAuthorityCount(sid)[0]
        advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
        advapi32.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        return int(advapi32.GetSidSubAuthority(sid, adet - 1)[0])
    finally:
        kernel32.CloseHandle(surec)


def kendini_yetkilendir():
    """Botu yönetici olarak yeniden başlatır. Başlatabildiyse True döner."""
    parametreler = subprocess.list2cmdline(sys.argv)
    sonuc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, parametreler, str(Path(__file__).parent), 1)
    return sonuc > 32


def pencereleri_listele():
    print("Açık pencereler:")
    for baslik in gw.getAllTitles():
        if baslik.strip():
            print(f"  - {baslik}")


def pencere_bul(ad, ekran_no=None):
    """Önce tam eşleşme, sonra 'içinde geçiyor' araması yapar.

    `ekran_no` verilirse sadece o ekrandaki pencereler aranır; iki oyun
    penceresi açıkken hangisinin sürüleceği böyle seçilir. O ekranda uygun
    pencere yoksa None döner (yanlış ekrandakine sessizce geçilmez).
    """
    pencereler = [w for w in gw.getAllWindows() if w.title.strip()]
    if ekran_no is not None:
        hedef = next((e for e in ekranlar() if e["no"] == ekran_no), None)
        if hedef is None:
            return None
        pencereler = [w for w in pencereler if ekranda_mi(w, hedef)]
    for w in pencereler:
        if w.title.strip().lower() == ad.lower():
            return w
    for w in pencereler:
        if ad.lower() in w.title.lower():
            return w
    return None


def _on_getir_thread_bagla(hwnd):
    """Windows'un 'foreground lock' korumasını aşmak için input thread'lerini bağlar."""
    onceki = user32.GetForegroundWindow()
    bizim_thread = kernel32.GetCurrentThreadId()
    onceki_thread = user32.GetWindowThreadProcessId(onceki, None)
    user32.AttachThreadInput(onceki_thread, bizim_thread, True)
    try:
        user32.SetForegroundWindow(hwnd)
    finally:
        user32.AttachThreadInput(onceki_thread, bizim_thread, False)


def _on_getir_alt_hilesi(hwnd):
    """ALT'a kısaca basmak foreground kilidini açar, sonra pencere öne alınır."""
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(hwnd)


def odakla(pencere):
    """Pencereyi öne getirir. Başarılıysa True döner."""
    hwnd = pencere._hWnd
    if user32.GetForegroundWindow() == hwnd:
        return True

    if pencere.isMinimized:
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.2)

    for yontem in (
        lambda: user32.SwitchToThisWindow(hwnd, True),
        lambda: _on_getir_thread_bagla(hwnd),
        lambda: _on_getir_alt_hilesi(hwnd),
    ):
        yontem()
        time.sleep(0.3)
        if user32.GetForegroundWindow() == hwnd:
            return True

    return False


# --------------------------------------------------------------------------
# Görüntü işleme
# --------------------------------------------------------------------------

def pencere_goruntusu(pencere):
    """Pencerenin ekran görüntüsünü RGB dizi olarak döner.

    pyautogui.screenshot() yalnızca BİRİNCİL ekranı alıp bölgeyi ondan
    kırpıyor; oyun ikinci ekranda olunca kare siyah geliyor ve hiçbir şablon
    bulunamıyordu. Bu yüzden doğrudan tüm ekranları kapsayan görüntüden
    (all_screens=True) kırpıyoruz; koordinatlar sanal masaüstü koordinatları.
    """
    kare = ImageGrab.grab(bbox=(pencere.left, pencere.top,
                                pencere.left + pencere.width,
                                pencere.top + pencere.height),
                          all_screens=True)
    return np.array(kare.convert("RGB"))


def isim_maskesi(goruntu):
    """NPC isim renginde olan pikselleri beyaz, gerisini siyah yapar."""
    fark = np.abs(goruntu.astype(int) - np.array(ISIM_RENGI)).max(axis=2)
    return ((fark <= RENK_TOLERANSI) * 255).astype(np.uint8)


def isim_kutulari(maske, pencere_genisligi):
    """Maskedeki yazıları kutulara ayırır; minimap noktalarını eler."""
    genis = cv2.dilate(maske, np.ones((3, 15), np.uint8))
    adet, _, istatistik, _ = cv2.connectedComponentsWithStats(genis, 8)
    kutular = []
    for i in range(1, adet):
        x, y, w, h, alan = istatistik[i]
        if w < 25 or not (6 <= h <= 30):
            continue
        if x > pencere_genisligi - 300 and y < 220:  # sağ üstteki minimap
            continue
        kutular.append((int(x), int(y), int(w), int(h), int(alan)))
    return kutular


def sablon_olustur(pencere):
    """Ekrandaki en büyük NPC ismini şablon olarak kaydeder."""
    goruntu = pencere_goruntusu(pencere)
    maske = isim_maskesi(goruntu)
    kutular = isim_kutulari(maske, pencere.width)
    if not kutular:
        print("Ekranda NPC ismi bulunamadı. NPC'nin ismi görünürken tekrar dene.")
        return False

    print(f"{len(kutular)} isim bulundu:")
    for x, y, w, h, alan in kutular:
        print(f"  x={x} y={y} {w}x{h} (piksel={alan})")

    x, y, w, h, _ = max(kutular, key=lambda k: k[4])
    pay = 2
    kirpik = maske[max(0, y - pay):y + h + pay, max(0, x - pay):x + w + pay]
    png_yaz(SABLON_DOSYASI, kirpik)
    print(f"Şablon kaydedildi: {SABLON_DOSYASI.name} ({kirpik.shape[1]}x{kirpik.shape[0]})")
    return True


# cv2.imread/imwrite Türkçe karakterli yollarda çalışmıyor (klasör adı "Masaüstü"),
# bu yüzden dosyayı numpy ile okuyup imdecode/imencode kullanıyoruz.
def png_yaz(yol, goruntu):
    tamam, tampon = cv2.imencode(".png", goruntu)
    if not tamam:
        raise OSError(f"PNG kodlanamadı: {yol}")
    tampon.tofile(str(yol))


def png_oku(yol):
    veri = np.fromfile(str(yol), dtype=np.uint8)
    if veri.size == 0:
        return None
    return cv2.imdecode(veri, cv2.IMREAD_GRAYSCALE)


def gorsel_sablon_yukle(dosya, etiket, esik):
    """Arayüz şablonunu (düğme, eşya, sekme) okur; yoksa/bozuksa None döner."""
    if not dosya.exists():
        print(f"'{dosya.name}' bulunamadı; {etiket.lower()} aranamaz.")
        return None
    sablon = png_oku(dosya)
    if sablon is None or sablon.size == 0:
        print(f"'{dosya.name}' okunamadı.")
        return None
    print(f"{etiket}: {dosya.name} ({sablon.shape[1]}x{sablon.shape[0]})  eşik={esik}")
    return sablon


def sablon_yukle():
    if not SABLON_DOSYASI.exists():
        return None
    sablon = png_oku(SABLON_DOSYASI)
    if sablon is None or sablon.size == 0:
        return None
    return sablon


def npc_bul(pencere, sablon, esik):
    """Şablonu ekranda arar. Bulursa (ekran_x, ekran_y, skor), yoksa (None, None, skor)."""
    goruntu = pencere_goruntusu(pencere)
    maske = isim_maskesi(goruntu)
    if maske.shape[0] < sablon.shape[0] or maske.shape[1] < sablon.shape[1]:
        return None, None, 0.0

    sonuc = cv2.matchTemplate(maske, sablon, cv2.TM_CCOEFF_NORMED)
    _, skor, _, konum = cv2.minMaxLoc(sonuc)
    if skor < esik:
        return None, None, float(skor)

    merkez_x = konum[0] + sablon.shape[1] // 2
    merkez_y = konum[1] + sablon.shape[0] // 2
    ekran_x = pencere.left + merkez_x + TIK_KAYDIRMA[0]
    ekran_y = pencere.top + merkez_y + TIK_KAYDIRMA[1]
    return ekran_x, ekran_y, float(skor)


def goruntu_bul(pencere, sablon, esik, kare=None):
    """Verilen görüntüyü pencerede arar. Bulursa (ekran_x, ekran_y, skor), yoksa (None, None, skor).

    Arayüz görüntüleri (düğme, eşya simgesi) piksel piksel aynı çizildiği için
    gri tonlamalı şablon eşleştirmesi yeterli. `kare` verilirse yeni ekran
    görüntüsü alınmaz; aynı kareden birden çok şablon aranabilir.
    """
    goruntu = pencere_goruntusu(pencere) if kare is None else kare
    gri = cv2.cvtColor(goruntu, cv2.COLOR_RGB2GRAY)
    if gri.shape[0] < sablon.shape[0] or gri.shape[1] < sablon.shape[1]:
        return None, None, 0.0

    sonuc = cv2.matchTemplate(gri, sablon, cv2.TM_CCOEFF_NORMED)
    _, skor, _, konum = cv2.minMaxLoc(sonuc)
    if skor < esik:
        return None, None, float(skor)

    ekran_x = pencere.left + konum[0] + sablon.shape[1] // 2
    ekran_y = pencere.top + konum[1] + sablon.shape[0] // 2
    return ekran_x, ekran_y, float(skor)


def _parlak_maske(goruntu):
    """Görüntüdeki açık renkli (yazı) pikselleri beyaz, gerisini siyah yapar."""
    return ((goruntu > YAZI_ESIGI).astype(np.uint8) * 255)


def baslik_bul(pencere, sablon, kare=None):
    """Envanter başlığını yalnızca yazı piksellerinden arar.

    Metin2 pencereleri yarı saydam: arkadaki sahne değiştikçe düz şablon
    eşleşmesi 0.57 ile 1.00 arasında oynuyordu ve başlık kimi zaman
    bulunamıyordu. Yazıyı ikili hale getirince arka plan hesaba katılmıyor.
    """
    goruntu = pencere_goruntusu(pencere) if kare is None else kare
    gri = cv2.cvtColor(goruntu, cv2.COLOR_RGB2GRAY)
    sonuc = cv2.matchTemplate(_parlak_maske(gri), _parlak_maske(sablon),
                              cv2.TM_CCOEFF_NORMED)
    _, skor, _, konum = cv2.minMaxLoc(sonuc)
    if skor < ENVANTER_PENCERE_ESIGI:
        return None, None, float(skor)
    return (pencere.left + konum[0], pencere.top + konum[1], float(skor))


def bekleyip_bul(pencere, sablon, esik, sure):
    """Görüntü çıkana kadar (en fazla `sure` saniye) aralıklarla arar."""
    bitis = time.time() + sure
    en_iyi = 0.0
    while True:
        bitis += duraklamayi_bekle()  # duraklamada geçen süre aramadan sayılmasın
        x, y, skor = goruntu_bul(pencere, sablon, esik)
        en_iyi = max(en_iyi, skor)
        if x is not None:
            return x, y, skor
        if time.time() >= bitis:
            return None, None, en_iyi
        time.sleep(ARAMA_ARALIGI)


# --------------------------------------------------------------------------
# Akış
# --------------------------------------------------------------------------

def _mesajla_tikla(pencere, x, y, buton, adet, arasi):
    """Tıklamayı pencereye Windows mesajı olarak gönderir (imleci oynatmadan).

    SendInput ile gönderilen tıklamaları arayüz almadığında bu yöntem işe yarar.
    """
    hwnd = pencere._hWnd
    nokta = wintypes.POINT(int(x), int(y))
    user32.ScreenToClient(hwnd, ctypes.byref(nokta))
    lparam = (nokta.y << 16) | (nokta.x & 0xFFFF)
    bas, birak, mk = FARE_MESAJLARI[buton]

    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
    time.sleep(FARE_TASIMA_BEKLEME)
    for sira in range(adet):
        user32.PostMessageW(hwnd, bas, mk, lparam)
        time.sleep(TIK_BASILI_KALMA)
        user32.PostMessageW(hwnd, birak, 0, lparam)
        if sira < adet - 1:
            time.sleep(arasi)


def _tikla(x, y, buton, adet, arasi):
    """İmleci taşır, oyunun algılaması için bekler, sonra basıp bırakır.

    Arayüz düğmeleri fare HAREKETİ ile 'üzerine gelindi' durumuna geçtiği için
    hedefe iki adımda gidiliyor; tek seferlik ışınlanmada oyun hareketi kaçırıp
    tıklamayı yok sayabiliyor.
    """
    failsafe_kontrol()
    odak_saglama()
    if TIK_YONTEMI == "mesaj" and AKTIF_PENCERE is not None:
        _mesajla_tikla(AKTIF_PENCERE, x, y, buton, adet, arasi)
        return

    # İmleç hedefe kaydırılarak götürülür; ulaşamazsa mutlak konumla düzeltilir.
    if not fare_kaydir(x, y):
        fare_tasi(x, y)
    time.sleep(FARE_TASIMA_BEKLEME)
    for sira in range(adet):
        if sira and durduruldu():
            return
        fare_bas(buton)
        time.sleep(TIK_BASILI_KALMA)
        fare_birak(buton)
        if sira < adet - 1:
            time.sleep(arasi)


def sol_tikla(x, y):
    """Aynı noktaya TIK_SAYISI kadar sol tık gönderir."""
    _tikla(x, y, "left", TIK_SAYISI, TIK_ARASI)


def tek_sol_tik(x, y):
    """Tek sol tık (envanterde eşya alıp bırakmak için)."""
    _tikla(x, y, "left", 1, TIK_ARASI)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _GIRDI(ctypes.Structure):
    class _BIRLIK(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("dolgu", ctypes.c_ubyte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _BIRLIK)]


def _fare_olayi(bayraklar, x=0, y=0):
    """SendInput ile fare olayı gönderir (mutlak konum 0-65535 aralığına çevrilir)."""
    girdi = _GIRDI(type=INPUT_MOUSE)
    girdi.mi = _MOUSEINPUT(x, y, 0, bayraklar, 0, None)
    user32.SendInput(1, ctypes.byref(girdi), ctypes.sizeof(_GIRDI))


def fare_tasi(x, y):
    """İmleci gerçek bir fare hareketi olayıyla taşır.

    pyautogui SetCursorPos kullanıyor; o çağrı hareket olayı üretmediği için
    oyun imlecin yerini güncellemiyor ve tıklama boşa gidiyordu.

    Mutlak konum BİRİNCİL ekrana göre değil sanal masaüstüne göre (VIRTUALDESK)
    ölçekleniyor; yoksa imleç ikinci ekrandaki hedefe hiç ulaşamıyor.
    """
    sol, ust, genislik, yukseklik = sanal_ekran()
    nx = int(round((x - sol) * 65535 / max(genislik - 1, 1)))
    ny = int(round((y - ust) * 65535 / max(yukseklik - 1, 1)))
    _fare_olayi(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny)


def _yakina_atla(hedef_x, hedef_y):
    """Hedef uzaksa imleci hedefin KAYDIRMA_YAKIN_MESAFE kadar yakınına ışınlar.

    Kalan yol adım adım kapatıldığı için oyun yine hedefe doğru gerçek bir
    hareket görüyor; uzaktaki düz yol için 50-60 adım harcanmıyor.
    """
    if not KAYDIRMA_YAKIN_MESAFE:
        return

    simdi = pyautogui.position()
    dx, dy = hedef_x - simdi.x, hedef_y - simdi.y
    uzaklik = max(abs(dx), abs(dy))
    if uzaklik <= KAYDIRMA_YAKIN_MESAFE:
        return

    oran = (uzaklik - KAYDIRMA_YAKIN_MESAFE) / uzaklik
    fare_tasi(simdi.x + int(dx * oran), simdi.y + int(dy * oran))
    time.sleep(KAYDIRMA_BEKLEME)


def fare_kaydir(hedef_x, hedef_y):
    """İmleci ışınlamadan, bağıl adımlarla kaydırarak hedefe götürür.

    Oyun fareyi bağıl hareketten okuduğu için mutlak konuma atlamak yerine
    gerçek fare gibi adım adım ilerliyoruz. Uzun yolun sadece son bölümü
    adımlanır (bkz. _yakina_atla). Hedefe ulaşınca True döner.
    """
    _yakina_atla(hedef_x, hedef_y)

    for _ in range(KAYDIRMA_MAKS_ADIM):
        simdi = pyautogui.position()
        dx, dy = hedef_x - simdi.x, hedef_y - simdi.y
        if abs(dx) <= 1 and abs(dy) <= 1:
            return True

        uzunluk = max(abs(dx), abs(dy))
        if uzunluk > KAYDIRMA_ADIMI:
            dx = int(round(dx * KAYDIRMA_ADIMI / uzunluk))
            dy = int(round(dy * KAYDIRMA_ADIMI / uzunluk))
        if dx == 0 and dy == 0:  # yuvarlama sıfırladıysa en az 1 px oynat
            dx = 1 if hedef_x > simdi.x else -1 if hedef_x < simdi.x else 0
            dy = 1 if hedef_y > simdi.y else -1 if hedef_y < simdi.y else 0

        _fare_olayi(MOUSEEVENTF_MOVE, dx, dy)  # bağıl hareket (mutlak değil)
        time.sleep(KAYDIRMA_BEKLEME)

    return False


def fare_bas(buton):
    _fare_olayi(FARE_BAYRAKLARI[buton][0])


def fare_birak(buton):
    _fare_olayi(FARE_BAYRAKLARI[buton][1])


def odak_saglama():
    """Girdi göndermeden önce oyunun önde olduğundan emin olur.

    Metin2 odakta değilken fare hareketini işlemiyor: imleç düğmenin üstünde
    görünse bile düğme 'üzerine gelindi' durumuna geçmiyor ve tıklama boşa
    gidiyor. Araya başka bir pencere girdiyse oyun tekrar öne alınır.
    """
    if AKTIF_PENCERE is None:
        return True
    if user32.GetForegroundWindow() == AKTIF_PENCERE._hWnd:
        return True
    print("  (odak oyunda değil, geri alınıyor)")
    if not odakla(AKTIF_PENCERE):
        print("  ! oyun öne getirilemedi, girdi işlemeyebilir")
        return False
    time.sleep(ODAK_SONRASI_BEKLEME)
    return True


def failsafe_kontrol():
    """Fare tüm ekranların dış köşelerinden birindeyse dur.

    Köşeler sanal masaüstünün dışına göre alınıyor: iki ekran arasındaki iç
    köşeler (ör. 1919,0) sayılmaz, yoksa imleç ekranlar arası geçerken bota
    yanlışlıkla dur denmiş olurdu.
    """
    if not pyautogui.FAILSAFE:
        return
    x, y = pyautogui.position()
    sol, ust, genislik, yukseklik = sanal_ekran()
    sag, alt = sol + genislik - 1, ust + yukseklik - 1
    kose = ((sol, ust), (sag, ust), (sol, alt), (sag, alt))
    if (x, y) in kose:
        raise pyautogui.FailSafeException("Fare köşeye götürüldü.")


def _tus_olayi(tarama_kodu, birakildi):
    """Tek bir tuş bas/bırak olayını tarama koduyla gönderir."""
    bayraklar = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if birakildi else 0)
    girdi = _GIRDI(type=INPUT_KEYBOARD)
    girdi.ki = _KEYBDINPUT(0, tarama_kodu, bayraklar, 0, None)
    user32.SendInput(1, ctypes.byref(girdi), ctypes.sizeof(_GIRDI))


def tus_gonder(ad, adet=1):
    """Tuşa `adet` kez basar. pyautogui.press yerine tarama kodu kullanır,
    çünkü Metin2 (DirectInput) sanal tuş kodlarını görmezden geliyor."""
    kod = TARAMA_KODLARI[ad]
    odak_saglama()
    for sira in range(adet):
        _tus_olayi(kod, birakildi=False)
        time.sleep(TUS_BASILI_KALMA)
        _tus_olayi(kod, birakildi=True)
        if sira < adet - 1:
            time.sleep(TUS_ARASI)


def sag_tikla(x, y, adet=None):
    """Aynı noktaya `adet` kez, aralarında SAG_TIK_ARASI bekleyerek sağ tık gönderir."""
    _tikla(x, y, "right", SAG_TIK_SAYISI if adet is None else adet, SAG_TIK_ARASI)


def esyaya_sag_tikla(pencere, esya_sablon, esya_esigi, adet=None):
    """Market açıldıktan sonra eşyayı (hancer.png) bulup `adet` kez sağ tıklar."""
    adet = SAG_TIK_SAYISI if adet is None else adet
    x, y, skor = bekleyip_bul(pencere, esya_sablon, esya_esigi, ESYA_ARAMA_SURESI)
    if x is None:
        print(f"  {ESYA_DOSYASI.name} bulunamadı (en iyi {skor:.2f} < {esya_esigi})"
              f" - market açılmamış ya da eşya görünmüyor olabilir")
        return False
    print(f"  {ESYA_DOSYASI.name} bulundu (skor {skor:.2f}) -> ({x}, {y}) "
          f"{adet} sağ tık ({SAG_TIK_ARASI} sn arayla)")
    sag_tikla(x, y, adet)
    return True




def sekme_noktasi(pencere, pencere_sablon, sekme_no):
    """`sekme_no` (1-4) numaralı sekmenin ekran koordinatını başlığa göre hesaplar."""
    sol_ust_x, sol_ust_y, bskor = baslik_bul(pencere, pencere_sablon)
    if sol_ust_x is None:
        return None, None, bskor

    x = sol_ust_x + SEKME1_OFSET[0] + (sekme_no - 1) * SEKME_ADIMI
    y = sol_ust_y + SEKME1_OFSET[1]
    return x, y, bskor


def sekmeye_gec(pencere, pencere_sablon, sekme_no):
    """Verilen envanter sekmesine tıklar; geçtiğini piksel değişiminden doğrular."""
    if not ENVANTER_SEKMESI_TIKLA:
        print("  sekme tıklama kapalı, doğrudan devam ediliyor")
        time.sleep(SEKME_KONTROL_BEKLEME)
        return True

    x = y = None
    for arama in range(1, 4):
        x, y, skor = sekme_noktasi(pencere, pencere_sablon, sekme_no)
        if x is not None:
            break
        print(f"  envanter başlığı bulunamadı (en iyi {skor:.2f}), tekrar bakılıyor ({arama}/3)")
        time.sleep(SEKME_KONTROL_BEKLEME)

    if x is None:
        print("  ! envanter başlığı bulunamadı - sekme değiştirilemiyor,"
              " açık olan sekmeyle devam ediliyor")
        return True

    genislik, yukseklik = SEKME_BOLGESI

    def sekme_bolgesi():
        ust = y - pencere.top - yukseklik // 2
        sol = x - pencere.left - genislik // 2
        return pencere_goruntusu(pencere)[ust:ust + yukseklik,
                                          sol:sol + genislik].astype(int)

    print(f"  {sekme_no}. envanter sekmesi -> ({x}, {y})")

    for deneme in range(1, ENVANTER_DENEMESI + 1):
        if durduruldu():
            return False
        once = sekme_bolgesi()
        sol_tikla(x, y)
        time.sleep(SEKME_KONTROL_BEKLEME)

        degisim = float(np.abs(sekme_bolgesi() - once).mean())
        if degisim > SEKME_DEGISIM_ESIGI:
            print(f"  sekme geçti (görünüm değişti, fark {degisim:.1f})")
            return True
        print(f"  sekme değişmedi (fark {degisim:.1f}) ({deneme}/{ENVANTER_DENEMESI})")

    # Zaten o sekmedeysek görüntü hiç değişmez; bu bir hata değil, devam edilir.
    print(f"  görünüm değişmedi - muhtemelen zaten {sekme_no}. sekmedeydi, devam ediliyor")
    return True


def dukkan_kapat(pencere, kapat_sablon):
    x, y, skor = bekleyip_bul(pencere, kapat_sablon, DUKKAN_KAPAT_ESIGI, ESYA_ARAMA_SURESI)
    if x is None:
        print(f"  {DUKKAN_KAPAT_DOSYASI.name} bulunamadı (en iyi {skor:.2f})")
        return False
    x += DUKKAN_KAPAT_OFSET[0] - kapat_sablon.shape[1] // 2
    y += DUKKAN_KAPAT_OFSET[1] - kapat_sablon.shape[0] // 2
    print(f"  mağaza kapatma ikonu bulundu (skor {skor:.2f}) -> ({x}, {y}) sol tık")
    tek_sol_tik(x, y)
    time.sleep(MENU_BEKLEME)
    return True




def isaretli_kaydet(pencere, sablon, hedef_dosya):
    """En iyi eşleşmeyi kutu+artı ile işaretleyip verilen dosyaya kaydeder."""
    x, y, skor = goruntu_bul(pencere, sablon, 0.0)  # eşik yok: en iyi eşleşmeyi göster
    goruntu = cv2.cvtColor(pencere_goruntusu(pencere), cv2.COLOR_RGB2BGR)
    px, py = x - pencere.left, y - pencere.top
    yari_g, yari_y = sablon.shape[1] // 2, sablon.shape[0] // 2
    cv2.rectangle(goruntu, (px - yari_g, py - yari_y), (px + yari_g, py + yari_y), (0, 0, 255), 2)
    cv2.drawMarker(goruntu, (px, py), (0, 0, 255), cv2.MARKER_CROSS, 30, 2)
    png_yaz(hedef_dosya, goruntu)
    return x, y, skor


def nokta_isaretle(pencere, dosya_adi):
    """Şablonun bulunduğu noktayı ekran görüntüsüne işaretleyip isaret.png olarak kaydeder."""
    dosya = Path(__file__).with_name(dosya_adi)
    if not dosya.exists():
        print(f"'{dosya_adi}' bulunamadı.")
        return
    hedef = Path(__file__).with_name("isaret.png")
    x, y, skor = isaretli_kaydet(pencere, png_oku(dosya), hedef)
    print(f"{dosya_adi} en iyi eşleşme: ({x}, {y}) skor {skor:.3f}")
    print(f"İşaretli görüntü kaydedildi: {hedef.name} (kırmızı artı = tıklanacak nokta)")


def hover_testi(pencere, dosya_adi):
    """İmleci hedefin üstüne götürüp düğmenin görüntüsü değişiyor mu bakar.

    Değişmiyorsa oyun imlecin oraya geldiğini hiç görmüyor demektir (girdi yolu
    sorunu); değişiyorsa hover çalışıyor, sorun tıklama olayındadır.
    """
    dosya = Path(__file__).with_name(dosya_adi)
    if not dosya.exists():
        print(f"'{dosya_adi}' bulunamadı.")
        return
    sablon = png_oku(dosya)

    x, y, skor = goruntu_bul(pencere, sablon, 0.8)
    if x is None:
        print(f"{dosya_adi} ekranda yok (en iyi {skor:.2f}). Önce o pencereyi aç.")
        return
    print(f"{dosya_adi} bulundu: ({x}, {y}) skor {skor:.2f}")

    yuk, gen = sablon.shape[0], sablon.shape[1]
    ust = y - pencere.top - yuk // 2
    sol = x - pencere.left - gen // 2

    def dugme_bolgesi():
        return pencere_goruntusu(pencere)[ust:ust + yuk, sol:sol + gen].astype(int)

    # imleç uzaktayken
    odak_saglama()
    fare_tasi(pencere.left + 30, pencere.top + pencere.height - 30)
    time.sleep(0.4)
    uzak = dugme_bolgesi()

    # imleç düğmenin üstündeyken
    fare_tasi(x - 12, y - 12)
    time.sleep(FARE_TASIMA_BEKLEME)
    fare_tasi(x, y)
    time.sleep(0.4)
    ustunde = dugme_bolgesi()

    fark = float(np.abs(ustunde - uzak).mean())
    print(f"düğme bölgesindeki ortalama piksel farkı: {fark:.2f}")
    if fark < 2.0:
        print("HOVER YOK -> oyun imlecin geldiğini görmüyor.")
        print("  Fare hareketi oyuna ulaşmıyor demektir; şunu dene:")
        print(f"  python bot.py --tik-testi {dosya_adi} --tik-yontemi mesaj")
    else:
        print("HOVER VAR -> imleç oyuna ulaşıyor, sorun tıklama olayında.")
        print("  Basılı kalma süresini artırmayı ve mesaj yöntemini dene:")
        print(f"  python bot.py --tik-testi {dosya_adi} --tik-yontemi mesaj")

    hedef = Path(__file__).with_name("hover.png")
    kiyas = np.hstack([uzak.astype(np.uint8), ustunde.astype(np.uint8)])
    png_yaz(hedef, cv2.cvtColor(kiyas, cv2.COLOR_RGB2BGR))
    print(f"Karşılaştırma kaydedildi: {hedef.name} (sol: uzakta, sağ: üstünde)")


def tik_testi(pencere, dosya_adi):
    """Şablonu bulur, tıklar ve ekrandan kaybolup kaybolmadığına bakar."""
    dosya = Path(__file__).with_name(dosya_adi)
    if not dosya.exists():
        print(f"'{dosya_adi}' bulunamadı.")
        return
    sablon = png_oku(dosya)

    x, y, skor = goruntu_bul(pencere, sablon, 0.8)
    if x is None:
        print(f"{dosya_adi} ekranda yok (en iyi {skor:.2f}). Önce o pencereyi aç.")
        return

    print(f"{dosya_adi} bulundu: ({x}, {y}) skor {skor:.2f}")
    print(f"Tıklama yöntemi: {TIK_YONTEMI}")
    tek_sol_tik(x, y)
    time.sleep(EVET_KONTROL_BEKLEME)

    x2, _, skor2 = goruntu_bul(pencere, sablon, 0.8)
    if x2 is None:
        print(f"BAŞARILI: hedef kayboldu (skor {skor2:.2f}) -> bu yöntem çalışıyor")
    else:
        print(f"BAŞARISIZ: hedef hâlâ ekranda (skor {skor2:.2f}) -> diğer yöntemi dene:")
        digeri = "mesaj" if TIK_YONTEMI == "sendinput" else "sendinput"
        print(f"  python bot.py --tik-testi {dosya_adi} --tik-yontemi {digeri}")


def beklemeleri_olcekle(carpan):
    """Tüm bekleme sürelerini çarpanla ölçekler (1'den büyük = daha yavaş/güvenli)."""
    global ADIM_BEKLEME, YUKSELTME_BEKLEME, EVET_YERLESME_BEKLEME, EVET_KONTROL_BEKLEME
    global FARE_TASIMA_BEKLEME, TIK_BASILI_KALMA, KAYDIRMA_BEKLEME, ARAMA_ARALIGI
    global YENI_ESYA_BEKLEME, TUS_ARASI, SEKME_KONTROL_BEKLEME, EVET_KONTROL_ILK_BEKLEME

    ADIM_BEKLEME *= carpan
    YUKSELTME_BEKLEME *= carpan
    EVET_YERLESME_BEKLEME *= carpan
    EVET_KONTROL_ILK_BEKLEME *= carpan
    EVET_KONTROL_BEKLEME *= carpan
    FARE_TASIMA_BEKLEME *= carpan
    TIK_BASILI_KALMA *= carpan
    KAYDIRMA_BEKLEME *= carpan
    ARAMA_ARALIGI *= carpan
    YENI_ESYA_BEKLEME *= carpan
    TUS_ARASI *= carpan
    SEKME_KONTROL_BEKLEME *= carpan


def geri_sayim(saniye):
    for kalan in range(saniye, 0, -1):
        if durduruldu():
            return
        print(f"Başlıyor... {kalan}")
        time.sleep(1)


def evete_tikla(pencere, evet_sablon, x, y, skor, tur):
    """Onay düğmesine tıklar ve gerçekten basıldığını doğrular.

    Düğme hâlâ ekrandaysa tıklama işlememiş demektir; tekrar denenir.
    """
    time.sleep(EVET_YERLESME_BEKLEME)  # pencere yeni açıldıysa oturması için

    for deneme in range(1, EVET_DENEMESI + 1):
        # Tam merkez yerine biraz sağ alta basılıyor (imlecin ucu düğmenin
        # üstünde kalsın diye); nokta düğmenin içinde kalıyor.
        tik_x = x + EVET_TIK_KAYDIRMA[0]
        tik_y = y + EVET_TIK_KAYDIRMA[1]
        print(f"  [{tur}] Evet ({x}, {y}) skor {skor:.2f} -> ({tik_x}, {tik_y}) sol tık")
        tek_sol_tik(tik_x, tik_y)

        # Sabit süre beklemek yerine pencere kapanana kadar bakıyoruz: kapanır
        # kapanmaz devam edilir, tam süre yalnızca tıklama işlemediyse harcanır.
        time.sleep(EVET_KONTROL_ILK_BEKLEME)
        bitis = time.time() + EVET_KONTROL_BEKLEME
        while True:
            x2, y2, skor2 = goruntu_bul(pencere, evet_sablon, EVET_ESIGI)
            if x2 is None:
                return True
            if time.time() >= bitis:
                break
            time.sleep(ARAMA_ARALIGI)
        x, y, skor = x2, y2, skor2
        print(f"  [{tur}] Evet penceresi kapanmadı, tekrar ({deneme}/{EVET_DENEMESI})")

    print(f"  ! {EVET_DOSYASI.name} tıklaması {EVET_DENEMESI} denemede de işlemedi")
    hata_dosyasi = Path(__file__).with_name("hata_evet.png")
    try:
        isaretli_kaydet(pencere, evet_sablon, hata_dosyasi)
        print(f"    O anki ekran {hata_dosyasi.name} olarak kaydedildi"
              f" (kırmızı artı = tıklanan nokta)")
    except Exception as hata:  # teşhis görüntüsü botun akışını bozmasın
        print(f"    (teşhis görüntüsü kaydedilemedi: {hata})")
    return False


def envanter_hucreleri(pencere, pencere_sablon):
    """Envanterdeki tüm hücrelerin ekran koordinatlarını yılan sırasıyla döner.

    Konumlar başlık çubuğuna göre hesaplanır; envanter penceresi taşınsa da
    ızgara doğru yerde kalır. Yılan sırası (bir satır soldan sağa, sonraki
    sağdan sola) imlecin gereksiz yol katetmesini önler.
    """
    bx, by, skor = baslik_bul(pencere, pencere_sablon)
    if bx is None:
        return [], skor

    sol_ust_x = bx + IZGARA_ILK_HUCRE[0]
    sol_ust_y = by + IZGARA_ILK_HUCRE[1]

    noktalar = []
    for satir in range(IZGARA_SATIR):
        sutunlar = range(IZGARA_SUTUN) if satir % 2 == 0 else reversed(range(IZGARA_SUTUN))
        for sutun in sutunlar:
            noktalar.append((sol_ust_x + sutun * IZGARA_ADIMI,
                             sol_ust_y + satir * IZGARA_ADIMI))
    return noktalar, skor


def envanteri_tara(pencere, pencere_sablon, yeni_esya_sablon, hucre_sayisi=None):
    """Envanter hücrelerinin üstünden hızlıca geçerek yeni eşya parlamasını söndürür.

    `hucre_sayisi` verilirse ilk turda sadece o kadar hücre gezilir: yeni alınan
    hançerler envanterin baştaki boş kutularına düştüğü için 45 kutunun hepsini
    dolaşmak gereksiz. Parlayan eşya yine de kalırsa (eşya beklenmedik bir
    kutuya düşmüşse) sonraki turda envanterin tamamı taranır.
    """
    for tur in range(1, IZGARA_TUR_SINIRI + 1):
        noktalar, skor = envanter_hucreleri(pencere, pencere_sablon)
        if not noktalar:
            print(f"  envanter başlığı bulunamadı (en iyi {skor:.2f}) - tarama atlandı")
            return False

        taranacak = noktalar[:hucre_sayisi] if (tur == 1 and hucre_sayisi) else noktalar
        print(f"  envanter taranıyor ({len(taranacak)}/{len(noktalar)} hücre, {tur}. tur)")
        odak_saglama()
        for x, y in taranacak:
            if durduruldu():
                return False
            if not fare_kaydir(x, y):
                fare_tasi(x, y)
            time.sleep(HUCRE_BEKLEME)

        x, _, pskor = goruntu_bul(pencere, yeni_esya_sablon, YENI_ESYA_ESIGI)
        if x is None:
            print(f"  parlayan eşya kalmadı (en iyi {pskor:.2f})")
            return True
        print(f"  hâlâ parlayan eşya var (skor {pskor:.2f}) - tekrar taranıyor")

    print("  parlama sönmedi ama devam ediliyor")
    return True


def yukseltme_dongusu(pencere, hammer_sablon, esya_sablon, evet_sablon, esya_esigi):
    """Envanterdeki hançerler bitene kadar: çekiç -> hançer -> Evet.

    Bir tur takılırsa (tıklama arayüz yerine dünyaya gitmiş olabilir) ESC ile
    onay penceresi kapatılıp sıradaki tura geçilir; arka arkaya TUR_HATA_SINIRI
    kadar tur başarısız olursa durulur.
    """
    basarili = 0
    ustuste_hata = 0

    for tur in range(1, MAKS_YUKSELTME + 1):
        if durduruldu():
            print(f"  durduruldu (sökülen: {basarili})")
            return False

        # Tek ekran görüntüsünden ikisini birden arıyoruz (fazladan kare almıyoruz)
        kare = pencere_goruntusu(pencere)
        ex, ey, eskor = goruntu_bul(pencere, esya_sablon, esya_esigi, kare)
        if ex is None:
            print(f"  envanterde {ESYA_DOSYASI.name} kalmadı (en iyi {eskor:.2f})"
                  f" - yükseltme bitti, sökülen: {basarili}")
            return True

        hx, hy, hskor = goruntu_bul(pencere, hammer_sablon, HAMMER_ESIGI, kare)
        if hx is None:
            print(f"  {HAMMER_DOSYASI.name} bulunamadı (en iyi {hskor:.2f}) - çekiç bitmiş olabilir"
                  f" (sökülen: {basarili})")
            return False

        print(f"  [{tur}] çekiç ({hx}, {hy}) skor {hskor:.2f} -> sol tık")
        tek_sol_tik(hx, hy)
        time.sleep(ADIM_BEKLEME)

        print(f"  [{tur}] hançer ({ex}, {ey}) skor {eskor:.2f} -> sol tık")
        tek_sol_tik(ex, ey)

        vx, vy, vskor = bekleyip_bul(pencere, evet_sablon, EVET_ESIGI, EVET_ARAMA_SURESI)
        if vx is not None and evete_tikla(pencere, evet_sablon, vx, vy, vskor, tur):
            basarili += 1
            ustuste_hata = 0
            time.sleep(YUKSELTME_BEKLEME)
            continue

        if vx is None:
            print(f"  [{tur}] {EVET_DOSYASI.name} çıkmadı (en iyi {vskor:.2f})"
                  f" - tıklama arayüz yerine dünyaya gitmiş olabilir")

        ustuste_hata += 1
        if ustuste_hata >= TUR_HATA_SINIRI:
            print(f"  ! arka arkaya {ustuste_hata} tur başarısız - durduruldu"
                  f" (sökülen: {basarili})")
            return False

        time.sleep(YUKSELTME_BEKLEME)

    print(f"  ! üst sınıra ulaşıldı ({MAKS_YUKSELTME}) - sökülen: {basarili}")
    return False


def sekmeleri_isle(pencere, envanter_pencere_sablon, hammer_sablon, esya_sablon,
                   yeni_esya_sablon, evet_sablon, esya_esigi, hancer_adedi=None):
    """Envanter sekmelerini sırayla gezip her birindeki hançerleri söker.

    İlk sekmeye tıklanmaz: envanter her zaman 1. sekmede açık kabul edilir. Her
    sekmede önce yeni eşya parlaması söndürülür, sonra yükseltme yapılır.
    Sekmedeki hançerler bitince bir sonrakine geçilir; hepsi bitince 1. sekmeye
    geri dönülür ki sıradaki tur yine oradan başlasın.

    `hancer_adedi` parlama taramasını o kadar hücreyle sınırlar.
    """
    for sira, sekme_no in enumerate(SEKMELER):
        if durduruldu():
            return False

        print(f"  --- {sekme_no}. envanter sekmesi ---")
        if sira == 0:
            print("  (ilk sekmeye tıklanmıyor, zaten açık kabul ediliyor)")
        elif not sekmeye_gec(pencere, envanter_pencere_sablon, sekme_no):
            return False

        if not envanteri_tara(pencere, envanter_pencere_sablon, yeni_esya_sablon,
                              hancer_adedi):
            return False
        if not yukseltme_dongusu(pencere, hammer_sablon, esya_sablon, evet_sablon, esya_esigi):
            return False

    if durduruldu():
        return False

    # Sıradaki tur yine 1. sekmede başlasın diye başa dönülüyor.
    if len(SEKMELER) > 1:
        print(f"  --- {SEKMELER[0]}. sekmeye geri dönülüyor ---")
        sekmeye_gec(pencere, envanter_pencere_sablon, SEKMELER[0])

    print("  tüm sekmeler tarandı")
    return True


def tur_calistir(pencere, npc_sablon, market_sablon, dukkan_kapat_sablon, esya_sablon,
                 yeni_esya_sablon, envanter_pencere_sablon, hammer_sablon, evet_sablon,
                 esik, market_esigi, esya_esigi, hancer_adedi, dene):
    """NPC'ye tıklar, 'Marketi aç' düğmesine basar, açılan markette eşyaya sağ tıklar.

    Düğme çıkmadıysa NPC'ye tıklanamamış demektir; düğme bulunana kadar
    NPC tıklaması tekrarlanır (Ctrl+C ile durdurulur).
    """
    if not odakla(pencere):
        print("  ! Pencere öne getirilemedi.")
        return False

    deneme = 0
    while True:
        if durduruldu():
            return False
        deneme += 1
        x, y, skor = npc_bul(pencere, npc_sablon, esik)
        if x is None:
            print(f"  NPC bulunamadı (en iyi eşleşme {skor:.2f} < {esik}), tekrar deneniyor"
                  f" ({deneme}. deneme)")
            time.sleep(DENEME_ARASI)
            if dene:
                return False
            continue

        if dene:
            print(f"  NPC bulundu (skor {skor:.2f}) -> tıklanacak nokta ({x}, {y}) [deneme modu]")
        else:
            print(f"  NPC bulundu (skor {skor:.2f}) -> ({x}, {y}) sol tık")
            tek_sol_tik(x, y)

        time.sleep(MENU_BEKLEME)

        mx, my, mskor = goruntu_bul(pencere, market_sablon, market_esigi)
        if mx is not None:
            if dene:
                print(f"  'Marketi aç' bulundu (skor {mskor:.2f}) -> ({mx}, {my}) [deneme modu]")
                return True
            print(f"  'Marketi aç' bulundu (skor {mskor:.2f}) -> ({mx}, {my}) sol tık")
            tek_sol_tik(mx, my)
            if not esyaya_sag_tikla(pencere, esya_sablon, esya_esigi, hancer_adedi):
                return False
            if not dukkan_kapat(pencere, dukkan_kapat_sablon):
                return False

            if not sekmeleri_isle(pencere, envanter_pencere_sablon, hammer_sablon,
                                  esya_sablon, yeni_esya_sablon, evet_sablon, esya_esigi,
                                  hancer_adedi):
                return False
            return True

        print(f"  'Marketi aç' yok (en iyi {mskor:.2f} < {market_esigi}) -> NPC'ye tıklanmamış,"
              f" tekrar deneniyor ({deneme}. deneme)")
        if dene:  # deneme modunda tıklama yapılmadığı için menü hiç açılmaz
            return False
        time.sleep(DENEME_ARASI)


def hazirla(pencere_adi=PENCERE_ADI, esik=ESIK, market_esigi=MARKET_ESIGI,
            esya_esigi=ESYA_ESIGI, envanter_esigi=ENVANTER_PENCERE_ESIGI,
            ekran_no=None):
    """Oyun penceresini bulur ve tüm şablonları yükler.

    `ekran_no` None ise oyun hangi ekranda açıksa o kullanılır; sayı verilirse
    sadece o ekrandaki pencere aranır.

    (pencere, sablonlar) döner; bir eksik varsa (None, None).
    """
    global AKTIF_PENCERE

    pencere = pencere_bul(pencere_adi, ekran_no)
    if pencere is None:
        if ekran_no is not None:
            print(f"'{pencere_adi}' penceresi {ekran_no}. ekranda bulunamadı.")
            baska = pencere_bul(pencere_adi)
            if baska is not None:
                ekran = pencerenin_ekrani(baska)
                nerede = f"{ekran['no']}. ekranda" if ekran else "ekranların dışında"
                print(f"  (oyun {nerede} görünüyor: konum=({baska.left}, {baska.top}))")
            print()
        else:
            print(f"'{pencere_adi}' penceresi bulunamadı. Oyun açık mı?\n")
        ekranlari_listele()
        pencereleri_listele()
        return None, None
    AKTIF_PENCERE = pencere

    ekran = pencerenin_ekrani(pencere)
    ekran_bilgisi = ekran_etiketi(ekran) if ekran else "ekran belirlenemedi"
    print(f"Pencere: '{pencere.title}'  konum=({pencere.left}, {pencere.top})  "
          f"boyut={pencere.width}x{pencere.height}")
    print(f"Çalışılan ekran: {ekran_bilgisi}")
    seviye = pencere_butunluk_seviyesi(pencere)
    seviye_adi = {BUTUNLUK_ORTA: "orta", BUTUNLUK_YUKSEK: "yüksek (yönetici)"}.get(seviye, seviye)
    print(f"Oyunun bütünlük seviyesi: {seviye_adi} | bot yönetici mi: {yonetici_mi()}")
    if seviye == BUTUNLUK_YUKSEK and not yonetici_mi():
        print("! Oyun yönetici olarak çalışıyor, bot değil: girdiler oyuna ULAŞMAZ.")

    npc_sablon = sablon_yukle()
    if npc_sablon is None:
        print(f"Şablon yok ({SABLON_DOSYASI.name}). Önce 'python bot.py --sablon' çalıştır.")
        return None, None
    print(f"NPC şablonu: {SABLON_DOSYASI.name} ({npc_sablon.shape[1]}x{npc_sablon.shape[0]})"
          f"  eşik={esik}")

    sablonlar = {
        "npc": npc_sablon,
        "market": gorsel_sablon_yukle(MARKET_DOSYASI, "Market şablonu", market_esigi),
        "dukkan_kapat": gorsel_sablon_yukle(DUKKAN_KAPAT_DOSYASI, "Mağaza kapatma ikonu", DUKKAN_KAPAT_ESIGI),
        "esya": gorsel_sablon_yukle(ESYA_DOSYASI, "Eşya şablonu", esya_esigi),
        "yeni_esya": gorsel_sablon_yukle(YENI_ESYA_DOSYASI, "Yeni (parlayan) eşya",
                                         YENI_ESYA_ESIGI),
        "hammer": gorsel_sablon_yukle(HAMMER_DOSYASI, "Çekiç şablonu", HAMMER_ESIGI),
        "evet": gorsel_sablon_yukle(EVET_DOSYASI, "Evet şablonu", EVET_ESIGI),
        "envanter": gorsel_sablon_yukle(ENVANTER_PENCERE_DOSYASI, "Envanter penceresi",
                                        envanter_esigi),
    }
    if any(s is None for s in sablonlar.values()):
        return None, None

    print("Envanter sekmeleri:", ", ".join(f"{n}." for n in SEKMELER),
          "| sekme tıklama:", "açık" if ENVANTER_SEKMESI_TIKLA else "kapalı")
    return pencere, sablonlar


def dongu_calistir(pencere, sablonlar, hancer_adedi, tur_sayisi=1,
                   esik=ESIK, market_esigi=MARKET_ESIGI, esya_esigi=ESYA_ESIGI, dene=False):
    """Satın al + söktür döngüsünü `tur_sayisi` kez çalıştırır (0 = sonsuz)."""
    tur = 0
    try:
        while tur_sayisi <= 0 or tur < tur_sayisi:
            if durduruldu():
                print("Durduruldu.")
                break
            tur += 1
            toplam = "sonsuz" if tur_sayisi <= 0 else tur_sayisi
            print(f"\n=== TUR {tur}/{toplam} | {hancer_adedi} hançer ===")
            if not tur_calistir(pencere, sablonlar["npc"], sablonlar["market"], sablonlar["dukkan_kapat"],
                                sablonlar["esya"], sablonlar["yeni_esya"], sablonlar["envanter"], sablonlar["hammer"],
                                sablonlar["evet"], esik, market_esigi, esya_esigi,
                                hancer_adedi, dene):
                break
            if durduruldu() or (tur_sayisi > 0 and tur >= tur_sayisi):
                break
            time.sleep(BEKLEME)
    except pyautogui.FailSafeException:
        print("\nFailSafe: fare köşeye gitti, durduruldu.")
    except KeyboardInterrupt:
        print("\nDurduruldu.")

    print(f"Bitti ({tur} tur).")
    return tur


def main():
    global TIK_YONTEMI, AKTIF_PENCERE, TIK_BASILI_KALMA

    parser = argparse.ArgumentParser(description="METIN2 NPC tıklayıcı")
    parser.add_argument("--delay", type=int, default=5, help="başlamadan önceki geri sayım (saniye)")
    parser.add_argument("--loop", action="store_true", help="sonsuz döngü (Ctrl+C ile dur)")
    parser.add_argument("--tur", type=int, default=1,
                        help="kaç kez satın al + söktür döngüsü çalıştırılacak")
    parser.add_argument("--hancer", type=int, default=SAG_TIK_SAYISI,
                        help="her turda kaç hançer satın alınacak")
    parser.add_argument("--dene", action="store_true", help="tıklama, sadece hedefi bildir")
    parser.add_argument("--sablon", action="store_true", help="ekrandaki NPC isminden şablon oluştur")
    parser.add_argument("--esik", type=float, default=ESIK, help="NPC ismi eşleşme eşiği (0-1)")
    parser.add_argument("--market-esik", type=float, default=MARKET_ESIGI,
                        help="'Marketi aç' düğmesi eşleşme eşiği (0-1)")
    parser.add_argument("--esya-esik", type=float, default=ESYA_ESIGI,
                        help="hancer.png eşleşme eşiği (0-1)")
    parser.add_argument("--envanter-esik", type=float, default=ENVANTER_PENCERE_ESIGI,
                        help="envanter penceresi (başlık) eşleşme eşiği (0-1)")
    parser.add_argument("--pencere", default=PENCERE_ADI, help="odaklanılacak pencere başlığı")
    parser.add_argument("--liste", action="store_true", help="açık pencere başlıklarını listele ve çık")
    parser.add_argument("--ekran", type=int, default=None,
                        help="oyunun aranacağı ekran no (1 = soldaki); boş bırakılırsa"
                             " pencere hangi ekrandaysa orası kullanılır")
    parser.add_argument("--ekranlar", action="store_true",
                        help="bağlı ekranları listele ve çık")

    parser.add_argument("--isaretle", metavar="DOSYA.png",
                        help="şablonun bulunduğu noktayı isaret.png'ye çizip çıkar")
    parser.add_argument("--tik-testi", metavar="DOSYA.png",
                        help="şablonu bulup tıklar ve kaybolup kaybolmadığını bildirir")
    parser.add_argument("--hover-testi", metavar="DOSYA.png",
                        help="imleci hedefe götürüp düğmenin görüntüsü değişiyor mu ölçer")
    parser.add_argument("--tik-yontemi", choices=("sendinput", "mesaj"), default=TIK_YONTEMI,
                        help="tıklama yöntemi: sendinput (varsayılan) veya mesaj")
    parser.add_argument("--basili-sure", type=float, default=TIK_BASILI_KALMA,
                        help="fare tuşunun basılı kalma süresi (saniye)")
    parser.add_argument("--yetkisiz", action="store_true",
                        help="yönetici yetkisi almadan devam et (girdiler oyuna geçmeyebilir)")
    parser.add_argument("--bekleme-carpani", type=float, default=1.0,
                        help="tüm beklemeleri ölçekler: 2 = iki kat yavaş/güvenli,"
                             " 0.5 = iki kat hızlı")
    args = parser.parse_args()

    if args.ekranlar:
        ekranlari_listele()
        return

    if args.liste:
        pencereleri_listele()
        return

    pencere = pencere_bul(args.pencere, args.ekran)
    if pencere is None:
        nerede = f" {args.ekran}. ekranda" if args.ekran else ""
        print(f"'{args.pencere}' penceresi{nerede} bulunamadı. Oyun açık mı?\n")
        ekranlari_listele()
        pencereleri_listele()
        return

    TIK_YONTEMI = args.tik_yontemi
    TIK_BASILI_KALMA = args.basili_sure
    AKTIF_PENCERE = pencere
    if args.bekleme_carpani != 1.0:
        beklemeleri_olcekle(args.bekleme_carpani)
        print(f"Bekleme çarpanı: {args.bekleme_carpani}")

    seviye = pencere_butunluk_seviyesi(pencere)
    if seviye == BUTUNLUK_YUKSEK and not yonetici_mi() and not args.dene:
        print("\n! Oyun yönetici olarak çalışıyor, bot ise değil.")
        print("  Bu durumda Windows (UIPI) botun fare ve klavye girdisini oyuna İLETMEZ:")
        print("  imleç ekranda hareket eder ama oyun ne 'üzerine gelindi' görür ne de tıklamayı.")
        if args.yetkisiz:
            print("  --yetkisiz verildiği için yine de devam ediliyor (girdiler işlemeyecek).")
        else:
            print("  Bot yönetici olarak yeniden başlatılıyor...")
            if kendini_yetkilendir():
                print("  Yeni pencerede devam ediyor, bu pencere kapanabilir.")
            else:
                print("  ! Yetki alınamadı (UAC reddedildi). Oyunu yönetici olmadan başlatmayı"
                      " ya da botu 'Yönetici olarak çalıştır' ile açmayı dene.")
            return

    if args.sablon:
        odakla(pencere)
        time.sleep(0.5)
        sablon_olustur(pencere)
        return

    if args.isaretle:
        odakla(pencere)
        time.sleep(0.5)
        nokta_isaretle(pencere, args.isaretle)
        return

    if args.hover_testi:
        odakla(pencere)
        time.sleep(0.5)
        hover_testi(pencere, args.hover_testi)
        return

    if args.tik_testi:
        odakla(pencere)
        time.sleep(0.5)
        tik_testi(pencere, args.tik_testi)
        return



    _, sablonlar = hazirla(args.pencere, args.esik, args.market_esik,
                           args.esya_esik, args.envanter_esik, args.ekran)
    if sablonlar is None:
        return

    geri_sayim(args.delay)
    dongu_calistir(pencere, sablonlar, args.hancer,
                   0 if args.loop else args.tur,
                   args.esik, args.market_esik, args.esya_esik, args.dene)


if __name__ == "__main__":
    main()
