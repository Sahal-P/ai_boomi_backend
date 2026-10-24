import type { Answer } from "./api/assistant.ts";

const copies = {
  en: {
    answer: "From your household records", decline: "Outside what FinBoy answers", clarify: "FinBoy needs one more detail",
    evidence: "Supporting records", all: "all", showing: "showing", of: "of", sample: "a sample, not the full list",
    play: "Play answer", retry: "Try audio again", stop: "Stop audio", ready: "Audio ready — play", preparing: "Preparing audio…", cancel: "Cancel",
    playing: "Playing the answer aloud.", tooLong: "This answer is too long to play as audio; the full text is above.",
    locale: "en-IN",
  },
  hi: {
    answer: "आपके घरेलू रिकॉर्ड से", decline: "FinBoy इस सवाल का जवाब नहीं देता", clarify: "FinBoy को एक और जानकारी चाहिए",
    evidence: "संबंधित रिकॉर्ड", all: "कुल", showing: "दिखाए गए", of: "में से", sample: "यह नमूना है, पूरी सूची नहीं",
    play: "जवाब सुनें", retry: "ऑडियो फिर आज़माएँ", stop: "ऑडियो रोकें", ready: "ऑडियो तैयार है — सुनें", preparing: "ऑडियो तैयार हो रहा है…", cancel: "रद्द करें",
    playing: "जवाब सुनाया जा रहा है।", tooLong: "यह जवाब ऑडियो के लिए बहुत लंबा है; पूरा जवाब ऊपर पढ़ें।",
    locale: "hi-IN",
  },
  hinglish: {
    answer: "Aapke ghar ke records se", decline: "FinBoy is sawal ka jawab nahi deta", clarify: "FinBoy ko ek aur jaankari chahiye",
    evidence: "Sambandhit records", all: "kul", showing: "dikhaye gaye", of: "mein se", sample: "yeh namoona hai, poori list nahi",
    play: "Jawab sunein", retry: "Audio phir aazmayein", stop: "Audio rokein", ready: "Audio taiyaar hai — sunein", preparing: "Audio taiyaar ho raha hai…", cancel: "Radd karein",
    playing: "Jawab sunaya ja raha hai.", tooLong: "Yeh jawab audio ke liye bahut lamba hai; poora jawab upar padhein.",
    locale: "en-IN",
  },
  ml: {
    answer: "നിങ്ങളുടെ വീട്ടിലെ രേഖകളിൽ നിന്ന്", decline: "FinBoy ഈ ചോദ്യത്തിന് ഉത്തരം നൽകില്ല", clarify: "FinBoy-ക്ക് ഒരു വിവരം കൂടി വേണം",
    evidence: "അനുബന്ധ രേഖകൾ", all: "ആകെ", showing: "കാണിക്കുന്നത്", of: "ആകെയുള്ള", sample: "ഇത് സാമ്പിൾ മാത്രം, പൂർണ്ണ പട്ടികയല്ല",
    play: "ഉത്തരം കേൾക്കുക", retry: "ഓഡിയോ വീണ്ടും ശ്രമിക്കുക", stop: "ഓഡിയോ നിർത്തുക", ready: "ഓഡിയോ തയ്യാറാണ് — കേൾക്കുക", preparing: "ഓഡിയോ തയ്യാറാക്കുന്നു…", cancel: "റദ്ദാക്കുക",
    playing: "ഉത്തരം വായിക്കുന്നു.", tooLong: "ഈ ഉത്തരം ഓഡിയോയ്ക്ക് വളരെ നീളമുള്ളതാണ്; പൂർണ്ണ ഉത്തരം മുകളിൽ വായിക്കാം.",
    locale: "ml-IN",
  },
  manglish: {
    answer: "Ningalude veettile rekhakalil ninnu", decline: "FinBoy ee chodyathinu utharam nalkilla", clarify: "FinBoy-kku oru vivaram koodi venam",
    evidence: "Anubandha rekhakal", all: "aake", showing: "kaanikkunnathu", of: "aakeyulla", sample: "ithu sample mathram, poornna pattikayalla",
    play: "Utharam kelkkuka", retry: "Audio veendum sramikkuka", stop: "Audio nirthuka", ready: "Audio thayyaranu — kelkkuka", preparing: "Audio thayyarakkunnu…", cancel: "Raddakkuka",
    playing: "Utharam vaayikkunnu.", tooLong: "Ee utharam audio-kku valare neelamullathanu; poornna utharam mukalil vaayikkam.",
    locale: "en-IN",
  },
};

export function answerCopy(answer: Pick<Answer, "display_language" | "display_script">) {
  const key = answer.display_language === "hi"
    ? answer.display_script === "Latn" ? "hinglish" : "hi"
    : answer.display_language === "ml"
      ? answer.display_script === "Latn" ? "manglish" : "ml"
      : "en";
  return copies[key];
}

export function answerDate(value: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" }).format(new Date(value));
}

export function answerPeriod(start: string, end: string, locale: string): string {
  const first = new Date(`${start}T12:00:00+05:30`);
  const last = new Date(`${end}T12:00:00+05:30`);
  if (first.getUTCFullYear() === last.getUTCFullYear() && first.getUTCMonth() === last.getUTCMonth() && first.getUTCDate() === 1 && last.getUTCDate() === new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate()) {
    return new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "Asia/Kolkata" }).format(first);
  }
  return start === end ? answerDate(start, locale) : `${answerDate(start, locale)} – ${answerDate(end, locale)}`;
}
