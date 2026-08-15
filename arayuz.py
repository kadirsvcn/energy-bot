"""Energy Bot arayüzü: başlat/duraklat/kapat, hançer adedi, döngü ve ekran seçimi.

Bot ayrı bir iş parçacığında çalışır:
  - "Duraklat" botu güvenli bir adımda bekletir, düğme "Devam et"e döner ve
    basınca bot kaldığı yerden sürer. Duraklamışken fare kullanıcıda kalır.
  - "Kapat" botu tamamen durdurur; tekrar çalıştırmak için "Başlat" gerekir.
Botun ekrana yazdığı her şey alttaki kayıt kutusuna düşer.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk

import bot


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
        self.duraklat_dugmesi = ttk.Button(dugmeler, text="Duraklat",
                                           command=self.duraklat_devam, state="disabled")
        self.duraklat_dugmesi.pack(side="left", padx=6)
        self.kapat_dugmesi = ttk.Button(dugmeler, text="Kapat", command=self.botu_kapat,
                                        state="disabled")
        self.kapat_dugmesi.pack(side="left", padx=(0, 6))
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
        self.duraklat_dugmesi.configure(state="normal", text="Duraklat")
        self.kapat_dugmesi.configure(state="normal")
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
        self.duraklat_dugmesi.configure(state="disabled", text="Duraklat")
        self.kapat_dugmesi.configure(state="disabled")
        self.durum.set("Kapatıldı" if bot.durdurma_istendi() else "Bitti")

    def duraklat_devam(self):
        """Aynı düğme: çalışırken duraklatır, duraklamışken kaldığı yerden sürdürür."""
        if bot.duraklatildi():
            bot.devam_et()
            self.duraklat_dugmesi.configure(text="Duraklat")
            self.durum.set(f"Çalışıyor - {self.calisma_bilgisi}")
        else:
            bot.duraklat()
            self.duraklat_dugmesi.configure(text="Devam et")
            self.durum.set("Duraklatılıyor... (bulunduğu adımı bitirip bekleyecek)")

    def botu_kapat(self):
        """Botu tamamen durdurur; devam etmek yerine baştan başlatmak gerekir."""
        bot.durdur()
        self.durum.set("Kapatılıyor... (bulunduğu adımı bitiriyor)")
        self.duraklat_dugmesi.configure(state="disabled", text="Duraklat")
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
