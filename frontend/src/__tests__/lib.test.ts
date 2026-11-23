import { describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, errorMessage } from "@/lib/api";
import { formatDate, formatKunye, formatResmiGazete, formatScore } from "@/lib/format";
import { validateEmail, validatePassword, validateQuery } from "@/lib/validation";

describe("biçimlendirme", () => {
  it("tarihi gg.aa.yyyy yapar", () => {
    expect(formatDate("1970-02-12")).toBe("12.02.1970");
    expect(formatDate(null)).toBeNull();
    expect(formatDate("bozuk")).toBeNull();
  });

  it("künyeyi eksik alanları atlayarak üretir", () => {
    expect(
      formatKunye({ mahkeme: "Danıştay", kurul: "İçtihatları Birleştirme Kurulu", esas_no: "1969/2", karar_no: "1970/1", karar_tarihi: "1970-02-12" }),
    ).toBe("Danıştay İçtihatları Birleştirme Kurulu, E.1969/2, K.1970/1, 12.02.1970");
    expect(formatKunye({ mahkeme: "Danıştay", kurul: null, esas_no: null, karar_no: "1970/1", karar_tarihi: null })).toBe(
      "Danıştay, K.1970/1",
    );
  });

  it("Resmî Gazete bilgisini yalnızca tarih ve sayı birlikteyse gösterir", () => {
    expect(formatResmiGazete({ resmi_gazete_tarihi: "1970-05-12", resmi_gazete_sayisi: "13500" })).toBe(
      "Resmî Gazete 12.05.1970, sayı 13500",
    );
    expect(formatResmiGazete({ resmi_gazete_tarihi: "1970-05-12", resmi_gazete_sayisi: null })).toBeNull();
  });

  it("skoru yüzdeye çevirir ve sınırlar", () => {
    expect(formatScore(0.834)).toBe("%83");
    expect(formatScore(1.7)).toBe("%100");
    expect(formatScore(-1)).toBe("%0");
  });
});

describe("doğrulama", () => {
  it("şifre kuralları arka uçla aynı", () => {
    expect(validatePassword("kisa1")).toMatch(/en az 10/);
    expect(validatePassword("sadeceharfler")).toMatch(/harf ve bir rakam/);
    expect(validatePassword("1234567890")).toMatch(/harf ve bir rakam/);
    expect(validatePassword(" bosluklu-sifre1")).toMatch(/boşluk/);
    expect(validatePassword("güvenli-şifre-1")).toBeNull();
  });

  it("e-posta ve olay metni", () => {
    expect(validateEmail("avukat@ornek.com")).toBeNull();
    expect(validateEmail("gecersiz")).not.toBeNull();
    expect(validateQuery("kısa")).toMatch(/en az 30/);
    expect(validateQuery("a".repeat(40))).toBeNull();
  });
});

describe("API istemcisi", () => {
  it("FastAPI hata gövdelerini Türkçe mesaja çevirir", () => {
    expect(errorMessage(401, { detail: "E-posta adresi veya şifre hatalı" })).toBe("E-posta adresi veya şifre hatalı");
    expect(errorMessage(422, { detail: [{ loc: ["body", "password"], msg: "String should have at least 10 characters" }] })).toMatch(
      /Şifre en az 10/,
    );
    expect(errorMessage(500, null)).toMatch(/Sunucuda/);
  });

  it("çerezle istek atar ve hata durumunda ApiError fırlatır", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Oturum açmanız gerekiyor" }), { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiFetch("/auth/me")).rejects.toEqual(new ApiError(401, "Oturum açmanız gerekiyor"));
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
  });

  it("ağ hatasını anlaşılır mesaja çevirir", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiFetch("/auth/me")).rejects.toMatchObject({ status: 0, message: expect.stringMatching(/ulaşılamadı/) });
  });
});
