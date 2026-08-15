# energy-bot

"""METIN2 NPC tıklayıcı.

Sabit koordinat yerine NPC'yi ekranda GÖRÜNTÜDEN bulur: Metin2 NPC isimlerini
sabit bir yeşil tonda (122, 231, 93) yazar. Bot ekran görüntüsündeki bu yeşil
yazıları maskeler ve kayıtlı şablonla (sablon_npc.png) eşleştirir; eşleşen ismin
biraz altına tıklar. Böylece karakter/kamera hareket etse de doğru yere basar.

Tıkladıktan sonra açılan menüdeki 'Marketi aç' düğmesini (open-market.png)
ekranda arar ve ona da tıklar. Düğme çıkmadıysa NPC'ye tıklanamamış demektir;
düğme bulunana kadar NPC tıklaması tekrarlanır.

Market açıldıktan sonra hancer.png ekranda aranır ve üzerine SAĞ tıklanır.
Ardından 3 kez ESC ve envanter tuşu ("ı") gönderilir. Tuşlar tarama koduyla
(scan code) gönderilir; Metin2 sanal tuş kodlarını görmezden geldiği için
pyautogui.press ile ESC işlemiyordu. 1. envanter sekmesini arayıp tıklama adımı
kapalı (ENVANTER_SEKMESI_TIKLA = False).

Envanter 1. sekmede açık kabul edilir (ona tıklanmaz). Her sekmede parlayan yeni
hançer varsa (new-hancer.png) bütün hücreler (5x9 ızgara) hızlıca taranıp parlama
söndürülür, sonra o sekme söktürülür; 1. sekme bitince 2. sekmeye geçilir. Ardından yükseltme döngüsü: envanterde
hançer kaldığı sürece çekiç (hammer.png), hançer (hancer.png) ve onay düğmesi
(evet.png) tıklanır.

Fare de tuşlar gibi SendInput ile sürülür: imleç gerçek hareket olaylarıyla
taşınır (SetCursorPos hareket olayı üretmediği için oyun tıklamayı boşa
harcıyordu), sonra basılı tutup bırakılır.

Tıklamalar: NPC ve market düğmesine 1 sol tık, envanter sekmesine 2 sol tık,
satın alırken eşyaya 1 saniye arayla 5 sağ tık.

Kullanım:
    python bot.py               -> NPC'yi bul ve 1 kez tıkla
    python bot.py --loop        -> sürekli bul ve tıkla (Ctrl+C ile dur)
    python bot.py --dene        -> tıklamadan sadece nereye basacağını yazar
    python bot.py --sablon      -> ekrandaki NPC isminden yeni şablon oluşturur
    python bot.py --esik 0.5    -> eşleşme eşiğini düşür/yükselt (varsayılan 0.6)
    python bot.py --delay 3     -> geri sayımı 3 saniye yapar
    python bot.py --liste       -> açık pencere başlıklarını listeler
    python bot.py --pencere X   -> başka bir pencere başlığı kullan
    python bot.py --ekranlar    -> bağlı ekranları (monitörleri) listeler
    python bot.py --ekran 2     -> sadece 2. ekrandaki oyun penceresini kullan

ÖNEMLİ: METIN2 yönetici olarak çalıştığı için bot da yönetici olmalı, yoksa
Windows tıklamaları oyuna iletmez. baslat.bat bunu kendisi ister.

Acil durdurma: fareyi ekranın sol üst köşesine (0,0) götür -> pyautogui FailSafe.
"""