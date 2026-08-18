"""Energy Bot arayüzü: başlat/duraklat/kapat, hançer adedi, döngü ve ekran seçimi.

Bot ayrı bir iş parçacığında çalışır:
  - "Duraklat" botu güvenli bir adımda bekletir, düğme "Devam et"e döner ve
    basınca bot kaldığı yerden sürer. Duraklamışken fare kullanıcıda kalır.
    Kısayolu P; oyun öndeyken de işler.
  - "Kapat" botu tamamen durdurur; tekrar çalıştırmak için "Başlat" gerekir.
Botun ekrana yazdığı her şey alttaki kayıt kutusuna düşer.
"""

import ctypes
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

import bot

# Duraklat/devam kısayolu. Harflerin sanal tuş kodu büyük harfin ASCII değeri.
KISAYOL_TUSU = "P"
KISAYOL_VK = ord(KISAYOL_TUSU)
KISAYOL_YOKLAMA = 50  # tuşa bakma aralığı (ms)
VK_CONTROL = 0x11
VK_MENU = 0x12  # ALT

DURAKLAT_YAZISI = f"Duraklat ({KISAYOL_TUSU})"
DEVAM_YAZISI = f"Devam et ({KISAYOL_TUSU})"

_user32 = ctypes.windll.user32
_user32.GetAsyncKeyState.restype = ctypes.c_short


def tus_durumu(vk):
    """(şu an basılı mı, son bakıştan beri basıldı mı) döner. Odaktan bağımsız.

    Düşük bit "bu çağrıdan önce basıldı" demek: iki yoklama arasına sıkışan
    hızlı bir dokunuş yalnızca 'şu an basılı' bilgisine bakınca kaçardı.
    """
    durum = _user32.GetAsyncKeyState(vk)
    return bool(durum & 0x8000), bool(durum & 0x0001)


def tus_basili(vk):
    return tus_durumu(vk)[0]


class Yazici:
    """print çıktısını arayüzdeki kutuya taşıyan dosya benzeri nesne."""

    def __init__(self, kuyruk):
        self.kuyruk = kuyruk

    def write(self, metin):
        if metin:
            self.kuyruk.put(metin)

    def flush(self):
        pass


class Arayuz:
    def __init__(self, kok):
        self.kok = kok
        self.kuyruk = queue.Queue()
        self.is_parcacigi = None
        self.calisma_bilgisi = ""  # durum satırında "Devam et" sonrası geri yazılır
        self.kisayol_basiliydi = False
        self.degistirici_basiliydi = False

        kok.title("Energy Bot")
        kok.geometry("720x520")
        kok.minsize(600, 400)

        ayarlar = ttk.Frame(kok, padding=10)
        ayarlar.pack(fill="x")

        ttk.Label(ayarlar, text="Hançer adedi:").grid(row=0, column=0, sticky="w")
        self.hancer = tk.StringVar(value="5")
        ttk.Spinbox(ayarlar, from_=1, to=200, width=8,
                    textvariable=self.hancer).grid(row=0, column=1, padx=(6, 20))

        ttk.Label(ayarlar, text="Döngü sayısı (0 = sonsuz):").grid(row=0, column=2, sticky="w")
        self.tur = tk.StringVar(value="1")
        ttk.Spinbox(ayarlar, from_=0, to=999, width=8,
                    textvariable=self.tur).grid(row=0, column=3, padx=6)

        ttk.Label(ayarlar, text="Geri sayım (sn):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.gecikme = tk.StringVar(value="3")
        ttk.Spinbox(ayarlar, from_=0, to=60, width=8,
                    textvariable=self.gecikme).grid(row=1, column=1, padx=(6, 20), pady=(8, 0))

        # Oyun ikinci ekranda açıksa "Otomatik" yeter; iki oyun penceresi
        # açıkken hangisinin sürüleceğini seçmek için ekran no verilir.
        ttk.Label(ayarlar, text="Ekran:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.ekran = tk.StringVar()
        self.ekran_kutusu = ttk.Combobox(ayarlar, textvariable=self.ekran, width=34,
                                         state="readonly")
        self.ekran_kutusu.grid(row=2, column=1, columnspan=2, padx=6, pady=(8, 0), sticky="w")
        ttk.Button(ayarlar, text="Yenile",
                   command=self.ekranlari_yukle).grid(row=2, column=3, padx=6, pady=(8, 0),
                                                      sticky="w")
        self.ekranlari_yukle()

        dugmeler = ttk.Frame(kok, padding=(10, 0))
        dugmeler.pack(fill="x")
        self.baslat_dugmesi = ttk.Button(dugmeler, text="Başlat", command=self.baslat)
        self.baslat_dugmesi.pack(side="left")
        self.duraklat_dugmesi = ttk.Button(dugmeler, text=DURAKLAT_YAZISI,
                                           command=self.duraklat_devam, state="disabled")
        self.duraklat_dugmesi.pack(side="left", padx=6)
        self.kapat_dugmesi = ttk.Button(dugmeler, text="Kapat", command=self.botu_kapat,
                                        state="disabled")
        self.kapat_dugmesi.pack(side="left", padx=(0, 6))
        self.enerji_dugmesi = ttk.Button(dugmeler, text="Enerji Parçası Ayır",
                                         command=self.enerji_ayir)
        self.enerji_dugmesi.pack(side="left", padx=(0, 6))
        ttk.Button(dugmeler, text="Kaydı temizle", command=self.temizle).pack(side="left")

        self.durum = tk.StringVar(value="Hazır")
        ttk.Label(kok, textvariable=self.durum, padding=(10, 6)).pack(fill="x")

        cerceve = ttk.Frame(kok, padding=(10, 0, 10, 10))
        cerceve.pack(fill="both", expand=True)
        self.kayit = tk.Text(cerceve, wrap="word", height=15, state="disabled")
        kaydirma = ttk.Scrollbar(cerceve, command=self.kayit.yview)
        self.kayit.configure(yscrollcommand=kaydirma.set)
        self.kayit.pack(side="left", fill="both", expand=True)
        kaydirma.pack(side="right", fill="y")

        kok.protocol("WM_DELETE_WINDOW", self.pencereyi_kapat)
        self.kuyrugu_isle()
        self.kisayolu_izle()

        self.yaz(f"Kısayol: {KISAYOL_TUSU} = duraklat / devam et"
                 " (bot çalışırken, oyun öndeyken de geçerli)\n")
        if not bot.yonetici_mi():
            self.yaz("! Bot yönetici yetkisiyle çalışmıyor. Oyun yönetici olarak\n"
                     "  çalışıyorsa girdiler oyuna ulaşmaz; arayuz.bat ile açın.\n")

    # ------------------------------------------------------------------
    def yaz(self, metin):
        self.kayit.configure(state="normal")
        self.kayit.insert("end", metin)
        self.kayit.see("end")
        self.kayit.configure(state="disabled")

    def temizle(self):
        self.kayit.configure(state="normal")
        self.kayit.delete("1.0", "end")
        self.kayit.configure(state="disabled")

    def kuyrugu_isle(self):
        """Bot iş parçacığının yazdıklarını arayüze aktarır (100 ms'de bir)."""
        try:
            while True:
                self.yaz(self.kuyruk.get_nowait())
        except queue.Empty:
            pass
        self.kok.after(100, self.kuyrugu_isle)

    def bot_calisiyor(self):
        return self.is_parcacigi is not None and self.is_parcacigi.is_alive()

    def kisayolu_izle(self):
        """P tuşuna basılmasını izler; basıldıysa duraklatır/devam ettirir.

        Tuşu RegisterHotKey ile kilitlemiyoruz, sadece basılı mı diye bakıyoruz:
        böylece P oyuna da ulaşmaya devam eder, kimseden çalınmaz. Kısayol
        yalnızca bot çalışırken iş görür; basılı tutmak bir kez sayılır.

        Ctrl/ALT ile birlikte basıldığında (Ctrl+P gibi) sayılmaz; değiştirici
        bir önceki bakışta basılıysa da atlanır, çünkü tuş bırakıldıktan sonra
        hangi değiştiriciyle basıldığı artık okunamıyor.
        """
        basili, yeni_basildi = tus_durumu(KISAYOL_VK)
        degistirici = tus_basili(VK_CONTROL) or tus_basili(VK_MENU)
        tetik = (yeni_basildi or (basili and not self.kisayol_basiliydi))
        if tetik and not degistirici and not self.degistirici_basiliydi and self.bot_calisiyor():
            self.duraklat_devam()
        self.kisayol_basiliydi = basili
        self.degistirici_basiliydi = degistirici
        self.kok.after(KISAYOL_YOKLAMA, self.kisayolu_izle)

    def ekranlari_yukle(self):
        """Ekran listesini tazeler. 'Otomatik' = oyun hangi ekrandaysa orası."""
        onceki = self.ekran.get()
        self.ekran_secenekleri = {"Otomatik (oyunun ekranı)": None}
        for ekran in bot.ekranlar():
            self.ekran_secenekleri[bot.ekran_etiketi(ekran)] = ekran["no"]

        secenekler = list(self.ekran_secenekleri)
        self.ekran_kutusu.configure(values=secenekler)
        self.ekran.set(onceki if onceki in self.ekran_secenekleri else secenekler[0])

    def ekran_no_al(self):
        return self.ekran_secenekleri.get(self.ekran.get())

    def sayi_al(self, degisken, ad, en_az):
        try:
            deger = int(degisken.get())
        except ValueError:
            self.yaz(f"! {ad} bir sayı olmalı.\n")
            return None
        if deger < en_az:
            self.yaz(f"! {ad} en az {en_az} olmalı.\n")
            return None
        return deger

    # ------------------------------------------------------------------
    def baslat(self):
        if self.is_parcacigi and self.is_parcacigi.is_alive():
            return

        hancer = self.sayi_al(self.hancer, "Hançer adedi", 1)
        tur = self.sayi_al(self.tur, "Döngü sayısı", 0)
        gecikme = self.sayi_al(self.gecikme, "Geri sayım", 0)
        if None in (hancer, tur, gecikme):
            return

        ekran_no = self.ekran_no_al()

        bot.durdurmayi_sifirla()
        self.calisma_bilgisi = (f"{hancer} hançer, {'sonsuz' if tur == 0 else tur} tur, "
                                f"{'otomatik ekran' if ekran_no is None else f'ekran {ekran_no}'}")
        self.baslat_dugmesi.configure(state="disabled")
        self.duraklat_dugmesi.configure(state="normal", text=DURAKLAT_YAZISI)
        self.kapat_dugmesi.configure(state="normal")
        self.enerji_dugmesi.configure(state="disabled")
        self.durum.set(f"Çalışıyor - {self.calisma_bilgisi}")

        self.is_parcacigi = threading.Thread(
            target=self.calis, args=(hancer, tur, gecikme, ekran_no), daemon=True)
        self.is_parcacigi.start()

    def calis(self, hancer, tur, gecikme, ekran_no):
        import contextlib
        yazici = Yazici(self.kuyruk)
        try:
            with contextlib.redirect_stdout(yazici):
                pencere, sablonlar = bot.hazirla(ekran_no=ekran_no)
                if sablonlar is None:
                    return
                bot.geri_sayim(gecikme)
                bot.dongu_calistir(pencere, sablonlar, hancer, tur)
        except Exception as hata:  # arayüz çökmesin, sebebi kayda düşsün
            self.kuyruk.put(f"\n! Hata: {hata}\n")
        finally:
            self.kok.after(0, self.bitti)

    def bitti(self):
        self.baslat_dugmesi.configure(state="normal")
        self.duraklat_dugmesi.configure(state="disabled", text=DURAKLAT_YAZISI)
        self.kapat_dugmesi.configure(state="disabled")
        self.enerji_dugmesi.configure(state="normal")
        self.durum.set("Kapatıldı" if bot.durdurma_istendi() else "Bitti")

    def enerji_ayir(self):
        """1. sekmedeki enerji parçasını ayırıp ilk boş hücreye yerleştirir (tek seferlik)."""
        if self.bot_calisiyor():
            return

        ekran_no = self.ekran_no_al()

        bot.durdurmayi_sifirla()
        self.baslat_dugmesi.configure(state="disabled")
        self.enerji_dugmesi.configure(state="disabled")
        self.kapat_dugmesi.configure(state="normal")
        self.durum.set("Enerji parçası ayrılıyor... (her"
                        f" {bot.ENERJI_DONGU_BEKLEME:g} sn'de bir, 'Kapat'a kadar)")

        self.is_parcacigi = threading.Thread(
            target=self.enerji_ayir_calis, args=(ekran_no,), daemon=True)
        self.is_parcacigi.start()

    def enerji_ayir_calis(self, ekran_no):
        import contextlib
        yazici = Yazici(self.kuyruk)
        try:
            with contextlib.redirect_stdout(yazici):
                pencere = bot.pencere_bul(bot.PENCERE_ADI, ekran_no)
                if pencere is None:
                    print(f"'{bot.PENCERE_ADI}' penceresi bulunamadı. Oyun açık mı?\n")
                    return
                bot.AKTIF_PENCERE = pencere

                envanter_sablon = bot.gorsel_sablon_yukle(
                    bot.ENVANTER_PENCERE_DOSYASI, "Envanter penceresi",
                    bot.ENVANTER_PENCERE_ESIGI)
                if envanter_sablon is None:
                    return

                if not bot.odakla(pencere):
                    print("  ! Pencere öne getirilemedi.")
                    return
                time.sleep(0.5)
                bot.enerji_ayir_dongusu(pencere, envanter_sablon)
        except Exception as hata:  # arayüz çökmesin, sebebi kayda düşsün
            self.kuyruk.put(f"\n! Hata: {hata}\n")
        finally:
            self.kok.after(0, self.enerji_ayir_bitti)

    def enerji_ayir_bitti(self):
        self.baslat_dugmesi.configure(state="normal")
        self.enerji_dugmesi.configure(state="normal")
        self.kapat_dugmesi.configure(state="disabled")
        self.durum.set("Kapatıldı" if bot.durdurma_istendi() else "Bitti")

    def duraklat_devam(self):
        """Aynı düğme: çalışırken duraklatır, duraklamışken kaldığı yerden sürdürür."""
        if bot.duraklatildi():
            bot.devam_et()
            self.duraklat_dugmesi.configure(text=DURAKLAT_YAZISI)
            self.durum.set(f"Çalışıyor - {self.calisma_bilgisi}")
        else:
            bot.duraklat()
            self.duraklat_dugmesi.configure(text=DEVAM_YAZISI)
            self.durum.set("Duraklatılıyor... (bulunduğu adımı bitirip bekleyecek)")

    def botu_kapat(self):
        """Botu tamamen durdurur; devam etmek yerine baştan başlatmak gerekir."""
        bot.durdur()
        self.durum.set("Kapatılıyor... (bulunduğu adımı bitiriyor)")
        self.duraklat_dugmesi.configure(state="disabled", text=DURAKLAT_YAZISI)
        self.kapat_dugmesi.configure(state="disabled")

    def pencereyi_kapat(self):
        bot.durdur()
        self.kok.destroy()


def main():
    kok = tk.Tk()
    Arayuz(kok)
    kok.mainloop()


if __name__ == "__main__":
    main()
