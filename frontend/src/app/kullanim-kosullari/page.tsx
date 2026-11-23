import { LegalPage } from "@/components/LegalPage";

export const metadata = { title: "Kullanım Koşulları — İçtihat Arama" };

export default function Page() {
  return (
    <LegalPage title="Kullanım Koşulları" updated="[GG.AA.YYYY]">
      <h2>1. Taraflar ve konu</h2>
      <p>
        Bu koşullar, [ŞİRKET UNVANI] (&quot;Şirket&quot;) tarafından sunulan İçtihat Arama hizmetinin
        (&quot;Hizmet&quot;) kullanımına ilişkindir. Hesap oluşturarak bu koşulları kabul etmiş olursunuz.
      </p>

      <h2>2. Hizmetin niteliği</h2>
      <ul>
        <li>
          Hizmet, girdiğiniz olay anlatımına göre içtihadı birleştirme kararlarını otomatik olarak sıralar ve
          açıklar. Sonuçlar hukuki görüş veya danışmanlık değildir; mesleki değerlendirmenin yerini tutmaz.
        </li>
        <li>
          Karar künyeleri ve metinleri resmî kaynaklarla doğrulanmaya çalışılır; doğrulanmamış kayıtlar uyarıyla
          gösterilir. Kullanmadan önce kararları Resmî Gazete veya ilgili yargı merciinin resmî kaynağından
          kontrol etmeniz gerekir.
        </li>
        <li>Otomatik açıklamalar hata içerebilir; açıklamaların karar metniyle uyumunu kontrol etmek kullanıcının sorumluluğundadır.</li>
      </ul>

      <h2>3. Hesap ve güvenlik</h2>
      <ul>
        <li>Hesap bilgilerinizin gizliliğinden siz sorumlusunuz; hesabınız başkalarıyla paylaşılamaz.</li>
        <li>Hizmetin otomatik araçlarla toplu sorgulanması, kopyalanması veya güvenliğinin aşılmaya çalışılması yasaktır.</li>
      </ul>

      <h2>4. Olay anlatımları ve gizlilik</h2>
      <p>
        Olay anlatımına müvekkillerinize ait kimlik bilgilerini (ad, T.C. kimlik no, adres vb.) yazmamanızı rica
        ederiz. Olay anlatımları kalıcı olarak saklanmaz; ayrıntılar için KVKK Aydınlatma Metni&apos;ne bakınız.
      </p>
      <p className="not">[Hukuki inceleme: avukatlık sır saklama yükümlülüğü (Av. K. m.36) açısından kullanıcı uyarısı değerlendirilmeli.]</p>

      <h2>5. Ücretlendirme ve abonelik</h2>
      <ul>
        <li>Abonelik olmadan her takvim ayında [3] ücretsiz arama hakkı tanınır.</li>
        <li>Abonelik ücreti [FİYAT] olup her dönem başında ödeme kuruluşu aracılığıyla otomatik olarak tahsil edilir.</li>
        <li>Aboneliğinizi istediğiniz zaman iptal edebilirsiniz; iptal sonrası yenileme yapılmaz, ödenmiş dönem sonuna kadar hizmet devam eder.</li>
        <li className="not">[Hukuki inceleme: Mesafeli Sözleşmeler Yönetmeliği kapsamında cayma hakkı, ön bilgilendirme formu ve mesafeli satış sözleşmesi ayrıca hazırlanmalı.]</li>
      </ul>

      <h2>6. Sorumluluğun sınırlandırılması</h2>
      <p>[Hukukçu tarafından düzenlenecek.]</p>

      <h2>7. Değişiklikler ve uyuşmazlıklar</h2>
      <p>
        Şirket bu koşulları güncelleyebilir; önemli değişiklikler kayıtlı e-posta adresinize bildirilir.
        Uyuşmazlıklarda [YETKİLİ MAHKEME / TÜKETİCİ HAKEM HEYETİ] yetkilidir.
      </p>

      <h2>8. İletişim</h2>
      <p>[E-POSTA ADRESİ] · [ADRES]</p>
    </LegalPage>
  );
}
