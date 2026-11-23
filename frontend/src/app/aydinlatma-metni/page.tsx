import { LegalPage } from "@/components/LegalPage";

export const metadata = { title: "KVKK Aydınlatma Metni — İçtihat Arama" };

export default function Page() {
  return (
    <LegalPage title="Kişisel Verilerin İşlenmesine İlişkin Aydınlatma Metni" updated="[GG.AA.YYYY]">
      <p>
        6698 sayılı Kişisel Verilerin Korunması Kanunu (&quot;KVKK&quot;) m.10 uyarınca, veri sorumlusu sıfatıyla
        [ŞİRKET UNVANI] (&quot;Şirket&quot;; MERSİS: [MERSİS NO]; adres: [ADRES]) olarak İçtihat Arama hizmeti
        kapsamında işlediğimiz kişisel verilere ilişkin sizi bilgilendiririz.
      </p>

      <h2>1. İşlenen kişisel veriler</h2>
      <ul>
        <li>Kimlik ve iletişim: e-posta adresi, (isteğe bağlı) ad soyad.</li>
        <li>Hesap güvenliği: şifrenizin geri döndürülemez özeti (şifrenin kendisi saklanmaz), oturum bilgileri.</li>
        <li>Müşteri işlem: abonelik durumu ve dönemi, ödeme kuruluşu tarafından verilen abonelik referans kodları.</li>
        <li>
          Kullanım: aylık arama sayısı ve arama sonuçlarında gösterilen karar kimlikleri. Arama için yazdığınız olay
          özeti kalıcı olarak saklanmaz ve günlük kayıtlarına yazılmaz.
        </li>
        <li>
          Ödeme: abonelik ödemesi sırasında girdiğiniz ad soyad, T.C. kimlik numarası, cep telefonu ve fatura adresi
          doğrudan ödeme kuruluşuna iletilir; Şirket tarafından saklanmaz. Kart bilgileriniz yalnızca ödeme
          kuruluşunun formunda girilir ve Şirkete ulaşmaz.
        </li>
      </ul>

      <h2>2. İşleme amaçları ve hukuki sebepler</h2>
      <ul>
        <li>Üyelik oluşturma, hizmetin sunulması ve abonelik yönetimi — sözleşmenin kurulması ve ifası (KVKK m.5/2-c).</li>
        <li>Fatura ve muhasebe yükümlülükleri — hukuki yükümlülük (m.5/2-ç).</li>
        <li>Hesap güvenliği, kötüye kullanımın önlenmesi, ücretsiz arama hakkının takibi — meşru menfaat (m.5/2-f).</li>
        <li className="not">[Hukuki inceleme: ticari elektronik ileti gönderilecekse ayrıca açık rıza/İYS süreci eklenmeli.]</li>
      </ul>

      <h2>3. Aktarım</h2>
      <ul>
        <li>Ödeme hizmeti: iyzico Ödeme Hizmetleri A.Ş. (abonelik ödemesi ve fatura bilgileri).</li>
        <li>Barındırma ve e-posta hizmet sağlayıcıları: [SAĞLAYICI ADLARI VE ÜLKELERİ].</li>
        <li>
          Açıklama hizmeti: arama sonuçlarında kararların neden uygun olduğunu açıklamak için olay özeti ve ilgili karar
          metni [YAPAY ZEKÂ HİZMET SAĞLAYICISI, ÜLKE] hizmetine iletilir.
        </li>
        <li className="not">
          [Hukuki inceleme: yurt dışında yerleşik sağlayıcılara aktarım KVKK m.9 kapsamında değerlendirilmeli
          (standart sözleşme / bildirim yükümlülüğü). Olay özetinde kişisel veri bulunabileceği için kullanıcı
          uyarısı ve aktarım dayanağı netleştirilmeli.]
        </li>
        <li>Yetkili kamu kurum ve kuruluşları: hukuki yükümlülük kapsamında talep halinde.</li>
      </ul>

      <h2>4. Toplama yöntemi</h2>
      <p>Kişisel verileriniz, internet sitesindeki formlar aracılığıyla elektronik ortamda toplanır.</p>

      <h2>5. Saklama süreleri</h2>
      <ul>
        <li>Hesap verileri: hesabınız silinene kadar. Hesabınızı &quot;Hesabım&quot; sayfasından silebilirsiniz.</li>
        <li>Fatura kayıtları: ilgili mevzuatta öngörülen süre boyunca [SÜRE].</li>
        <li>E-posta doğrulama ve şifre sıfırlama bağlantıları: en fazla 48 saat / 60 dakika geçerlidir.</li>
        <li>Olay özetleri: saklanmaz.</li>
      </ul>

      <h2>6. Haklarınız</h2>
      <p>
        KVKK m.11 uyarınca; kişisel verilerinizin işlenip işlenmediğini öğrenme, bilgi talep etme, işleme amacını
        öğrenme, aktarıldığı üçüncü kişileri bilme, eksik/yanlış işlenmişse düzeltilmesini, silinmesini veya yok
        edilmesini isteme, bu işlemlerin aktarılan üçüncü kişilere bildirilmesini isteme, otomatik sistemlerle
        analiz sonucu aleyhinize bir sonuç çıkmasına itiraz etme ve kanuna aykırı işleme nedeniyle zararın
        giderilmesini talep etme haklarına sahipsiniz.
      </p>
      <p>
        Başvurularınızı [E-POSTA / KEP ADRESİ] adresine veya [POSTA ADRESİ] adresine yazılı olarak iletebilirsiniz.
        Başvurular en geç otuz gün içinde sonuçlandırılır.
      </p>
    </LegalPage>
  );
}
