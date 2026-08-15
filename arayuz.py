"""Energy Bot arayüzü: başlat/durdur ve hançer adedi / döngü sayısı ayarları.

Bot ayrı bir iş parçacığında çalışır; "Durdur" botun durdurma bayrağını kurar,
bot da her adımda buna bakıp güvenli bir noktada çıkar. Botun ekrana yazdığı
her şey alttaki kayıt kutusuna düşer.
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

        kok.title("Energy Bot")
        kok.geometry("640x480")
        kok.minsize(520, 380)

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

        dugmeler = ttk.Frame(kok, padding=(10, 0))
        dugmeler.pack(fill="x")
        self.baslat_dugmesi = ttk.Button(dugmeler, text="Başlat", command=self.baslat)
        self.baslat_dugmesi.pack(side="left")
        self.durdur_dugmesi = ttk.Button(dugmeler, text="Durdur", command=self.durdur,
                                         state="disabled")
        self.durdur_dugmesi.pack(side="left", padx=6)
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

        kok.protocol("WM_DELETE_WINDOW", self.kapat)
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

        bot.durdurmayi_sifirla()
        self.baslat_dugmesi.configure(state="disabled")
        self.durdur_dugmesi.configure(state="normal")
        self.durum.set(f"Çalışıyor - {hancer} hançer, "
                       f"{'sonsuz' if tur == 0 else tur} tur")

        self.is_parcacigi = threading.Thread(
            target=self.calis, args=(hancer, tur, gecikme), daemon=True)
        self.is_parcacigi.start()

    def calis(self, hancer, tur, gecikme):
        import contextlib
        yazici = Yazici(self.kuyruk)
        try:
            with contextlib.redirect_stdout(yazici):
                pencere, sablonlar = bot.hazirla()
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
        self.durdur_dugmesi.configure(state="disabled")
        self.durum.set("Durduruldu" if bot.durduruldu() else "Bitti")

    def durdur(self):
        bot.durdur()
        self.durum.set("Durduruluyor... (bulunduğu adımı bitiriyor)")
        self.durdur_dugmesi.configure(state="disabled")

    def kapat(self):
        bot.durdur()
        self.kok.destroy()


def main():
    kok = tk.Tk()
    Arayuz(kok)
    kok.mainloop()


if __name__ == "__main__":
    main()
