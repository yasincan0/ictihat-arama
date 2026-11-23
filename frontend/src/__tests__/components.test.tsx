import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ResultCard } from "@/components/ResultCard";
import { SearchForm } from "@/components/SearchForm";
import { SearchView } from "@/components/SearchView";
import { VerificationBadge } from "@/components/VerificationBadge";
import type { SearchResult } from "@/lib/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const result = (over: Partial<SearchResult["karar"]> = {}): SearchResult => ({
  karar: {
    id: 1,
    mahkeme: "Danıştay",
    kurul: "İçtihatları Birleştirme Kurulu",
    esas_no: "1969/2",
    karar_no: "1970/1",
    karar_tarihi: "1970-02-12",
    resmi_gazete_tarihi: null,
    resmi_gazete_sayisi: null,
    ozet: "Test özeti",
    dogrulandi: false,
    dogrulama_kaynagi: null,
    ...over,
  },
  skor: 0.91,
  aciklama: "Test açıklaması",
  alinti: "Test alıntısı",
});

describe("VerificationBadge", () => {
  it("doğrulanmamış kararda uyarı gösterir", () => {
    render(<VerificationBadge verified={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("Doğrulanmamış");
  });
  it("doğrulanmış kararda kaynağı başlıkta taşır", () => {
    render(<VerificationBadge verified source="Resmî Gazete 12.05.1970, sayı 13500" />);
    expect(screen.getByText(/Resmî kaynaktan doğrulandı/).closest("span")).toHaveAttribute(
      "title",
      "Resmî Gazete 12.05.1970, sayı 13500",
    );
  });
});

describe("ResultCard", () => {
  it("künye, skor, açıklama, alıntı ve bağlantıyı gösterir", () => {
    render(<ResultCard result={result()} rank={1} />);
    expect(screen.getByRole("heading")).toHaveTextContent("Danıştay İçtihatları Birleştirme Kurulu, E.1969/2, K.1970/1, 12.02.1970");
    expect(screen.getByText("Benzerlik %91")).toBeInTheDocument();
    expect(screen.getByText("Test açıklaması")).toBeInTheDocument();
    expect(screen.getByText("Test alıntısı")).toBeInTheDocument();
    expect(screen.getByText(/Doğrulanmamış/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Karar ayrıntısı" })).toHaveAttribute("href", "/karar/1");
  });
  it("doğrulanmış kararda Resmî Gazete bilgisini gösterir", () => {
    render(<ResultCard result={result({ dogrulandi: true, resmi_gazete_tarihi: "1970-05-12", resmi_gazete_sayisi: "13500" })} rank={2} />);
    expect(screen.getByText("Resmî Gazete 12.05.1970, sayı 13500")).toBeInTheDocument();
    expect(screen.queryByText(/Doğrulanmamış/)).not.toBeInTheDocument();
  });
});

describe("SearchForm", () => {
  it("kısa metinde arama yapmaz, yeterli metinde yapar", async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    render(<SearchForm onSearch={onSearch} />);
    await user.type(screen.getByLabelText(/olayı anlatın/i), "çok kısa");
    await user.click(screen.getByRole("button", { name: /kararları bul/ }));
    expect(onSearch).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/en az 30/);

    await user.type(screen.getByLabelText(/olayı anlatın/i), " ama şimdi yeterince uzun bir olay anlatımı var");
    await user.click(screen.getByRole("button", { name: /kararları bul/ }));
    expect(onSearch).toHaveBeenCalledOnce();
  });
});

describe("SearchView", () => {
  it("örnek veri modunda uyarı ve örnek sonuçları gösterir", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));
    const user = userEvent.setup();
    render(<SearchView mock />);
    expect(screen.getByText(/örnek sonuçlar/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/olayı anlatın/i), "Müvekkilimin işyeri önceden bildirim yapılmadan mühürlendi.");
    await user.click(screen.getByRole("button", { name: /kararları bul/ }));
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(2));
    expect(screen.getAllByText(/ÖRNEK KAYIT/)).toHaveLength(2);
  });

  it("giriş zorunluysa ve oturum yoksa giriş ister", async () => {
    const { AuthProvider } = await import("@/components/AuthProvider");
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          url.endsWith("/config")
            ? new Response(JSON.stringify({ arama_giris_gerekli: true, abonelik_acik: false, aciklama_acik: false, karar_sayisi: 1, dogrulanmis_karar_sayisi: 0 }), { status: 200 })
            : new Response(JSON.stringify({ detail: "Oturum açmanız gerekiyor" }), { status: 401 }),
        ),
      ),
    );
    render(
      <AuthProvider>
        <SearchView mock={false} />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByRole("link", { name: "giriş yapın" })).toBeInTheDocument());
    expect(screen.queryByLabelText(/olayı anlatın/i)).not.toBeInTheDocument();
  });
});

describe("gerçek arama", () => {
  const CONFIG = { arama_giris_gerekli: false, abonelik_acik: false, aciklama_acik: true, karar_sayisi: 108, dogrulanmis_karar_sayisi: 0 };

  it("oturumsuz arar; künyesiz karar, uygun olmayan karar ve genel değerlendirmeyi gösterir", async () => {
    const { AuthProvider } = await import("@/components/AuthProvider");
    const body = {
      ornek_veri: false,
      aciklama_durumu: "tamam",
      genel_degerlendirme: "En uygun karar birincisidir.",
      sonuclar: [
        { ...result(), uygun: true },
        { ...result({ id: 2, esas_no: null, karar_no: null, karar_tarihi: null, kategori: "Personel" }), aciklama: "İlgisiz.", uygun: false, alinti: null },
      ],
    };
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith("/config")) return Promise.resolve(new Response(JSON.stringify(CONFIG), { status: 200 }));
      if (url.endsWith("/search")) return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ detail: "x" }), { status: 401 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <SearchView mock={false} />
      </AuthProvider>,
    );
    expect(await screen.findByText(/108 karar aranabilir/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/olayı anlatın/i), "Müvekkilimin işyeri önceden bildirim yapılmadan mühürlendi.");
    await user.click(screen.getByRole("button", { name: /kararları bul/ }));
    expect(await screen.findByText("En uygun karar birincisidir.")).toBeInTheDocument();
    expect(screen.getByText(/künyesi bilinmiyor \(Personel\)/)).toBeInTheDocument();
    expect(screen.getByText(/Künye eksik/)).toBeInTheDocument();
    expect(screen.getByText("Olaya uygun görünmüyor")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/search"))!;
    expect(JSON.parse((call[1] as RequestInit).body as string)).toEqual({ olay: "Müvekkilimin işyeri önceden bildirim yapılmadan mühürlendi." });
  });

  it("açıklama kapalıysa bunu belirtir", async () => {
    const { AuthProvider } = await import("@/components/AuthProvider");
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          url.endsWith("/config")
            ? new Response(JSON.stringify({ ...CONFIG, aciklama_acik: false }), { status: 200 })
            : url.endsWith("/search")
              ? new Response(JSON.stringify({ ornek_veri: false, aciklama_durumu: "kapali", sonuclar: [result()] }), { status: 200 })
              : new Response("{}", { status: 401 }),
        ),
      ),
    );
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <SearchView mock={false} />
      </AuthProvider>,
    );
    await user.type(await screen.findByLabelText(/olayı anlatın/i), "Müvekkilimin işyeri önceden bildirim yapılmadan mühürlendi.");
    await user.click(screen.getByRole("button", { name: /kararları bul/ }));
    expect(await screen.findByText(/API anahtarı tanımlı değil/)).toBeInTheDocument();
  });
});
