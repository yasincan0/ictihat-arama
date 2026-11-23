# İndirilecek resmî metinler (ilk deneme)

Bu liste `python -m data.pipeline.verify_official --liste` ile üretilir.

Resmî Gazete sitesi (www.resmigazete.gov.tr) bu geliştirme ortamından erişilemediği
için dosyaların elle indirilmesi gerekir. Danıştay İçtihatları Birleştirme Kurulu
kararları Resmî Gazete'de yayımlanır; yayım tarihi genellikle karar tarihinden
birkaç hafta ile birkaç ay sonradır. Listede Resmî Gazete tarih ve sayısı yoktur;
karar tarihinden sonraki sayılar taranarak bulunmalıdır.

## Nasıl kaydedilir

1. Kararın yayımlandığı Resmî Gazete sayısını (PDF veya HTML) indirin.
2. Dosyayı `data/raw/resmigazete/` klasörüne şu adla koyun:
   `rg-YYYYMMDD-SAYI_sira-N.pdf` (ör. `rg-19700512-13500_sira-5.pdf`).
   - `rg-YYYYMMDD-SAYI`: Resmî Gazete tarihi ve sayısı (doğrulama kaynağı olarak yazılır).
   - `sira-N`: aşağıdaki tablodaki sıra numarası (künye OCR ile okunamazsa eşleştirmeye
     yardım eder; isteğe bağlıdır).
3. `python -m data.pipeline.verify_official` komutunu çalıştırın; sonuç
   `docs/dogrulama_raporu.md` dosyasına yazılır.

Taranmış (görüntü) PDF'ler OCR ile okunur; tarama ne kadar net olursa sonuç o kadar
iyidir. Tek sayfalık görüntüler (.png, .jpg, .tif) de kabul edilir.

## Liste

| Sıra | Karar tarihi | Esas | Karar | Özet (ikincil kaynak) | Not |
|---:|---|---|---|---|---|
| 5 | 12.02.1970 | 1969/2 | 1970/1 | Parselasyon planlarına karşı açılan davalarda dava açma süresi, Anayasa'nın 114. maddesine göre yazılı bildirim tarihinden itibaren başlar. |  |
| 6 | 09.05.1970 | 1967/10 | 1970/24 | Danıştay'da dava açma ve cevap verme sürelerinin son günü tatile rastlarsa süre, izleyen ilk çalışma gününün sonunda biter. |  |
| 7 | 20.06.1970 | 1969/1 | 1970/27 | Emeklilik işlemi iptal edilip yeniden göreve alınanların emekli statüsünde geçen sürelerinin bir terfi dönemine denk gelen kısmı memuriyet kıdemine sayılır. Şart: uyuşmazlık daha önce Danıştayca karara bağlanmamış olmalı. |  |
| 11 | 24.02.1973 | 1970/1 | 1973/1 | Süre aşımı gözetilmeden esastan karara bağlanan davada, karar düzeltme aşamasında süre aşımı dikkate alınır. |  |
| 15 | 22.12.1973 | 1968/8 | 1973/14 | Kanuna aykırı terfi veya intibak sonucu fazla ödenen aylıklar, ilk kanunsuz ödemeden itibaren 90 gün içinde geri alınabilir. İstisna: yokluk, açık hata, memurun gerçek dışı beyanı veya hilesi hallerinde süre aranmaz. | Esas no başka kaynakta 1969/8 |
| 21 | 08.03.1979 | 1971/1 | 1979/1 | TMMOB'un dava açma ve davada taraf olma ehliyeti vardır. |  |
| 22 | 15.03.1979 | 1971/9 | 1979/5 | İdareye başvurmadan doğrudan tam yargı davası açılırsa, dilekçe davanın her aşamasında ilgili idareye gönderilir. |  |
| 23 | 28.06.1979 | 1976/1 | 1979/10 | Doğal afet zararında gelir kaynağını ve zarar derecesini il ve ilçe idare kurulları saptar; bu kararlar yargısal nitelik taşımaz. Verginin terkini konusunda karar vermek Maliye Bakanlığının yetkisindedir. |  |
| 24 | 12.06.1980 | 1977/1 | 1980/2 | Takdir komisyonuna başvurunun zamanaşımını durdurması kuralı ceza zamanaşımına uygulanmaz. |  |
| 26 | 29.12.1983 | 1969/3 | 1983/8 | Ertelenmiş mahkûmiyet nedeniyle, 657 sayılı Kanun'un 48/A-5 ve 98/b maddeleri uyarınca memurun görevine son verilemez. |  |
