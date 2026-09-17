export interface DiseaseProfile {
  name: string;
  family: string;
  route: string;
  summary: string;
  priorities: string[];
  url: string;
}
export const DISEASE_PROFILES: DiseaseProfile[] = [
  {
    name: "Ebola",
    family: "Viral disease",
    route: "Direct contact · body fluids",
    summary:
      "Ebola is a severe viral disease. Human transmission involves direct contact with infected blood or other body fluids, or contaminated materials.",
    priorities: [
      "Case detection and contact tracing",
      "Infection prevention in care settings",
      "Community engagement and safe burial practices",
    ],
    url: "https://www.who.int/news-room/fact-sheets/detail/ebola-disease",
  },
  {
    name: "Mpox",
    family: "Viral disease",
    route: "Close contact · contaminated materials",
    summary:
      "Mpox can spread through close contact with an infected person, contaminated materials, or infected animals. The disease can cause a painful rash and fever.",
    priorities: [
      "Timely diagnosis and contact identification",
      "Reduce exposure during infectious illness",
      "Vaccination according to official eligibility guidance",
    ],
    url: "https://www.who.int/news-room/fact-sheets/detail/mpox",
  },
  {
    name: "Avian influenza",
    family: "Zoonotic influenza",
    route: "Exposure to infected animals or environments",
    summary:
      "Animal influenza viruses can infect people, usually following exposure to infected animals or contaminated environments. Risks differ between virus subtypes and outbreaks.",
    priorities: [
      "Coordinated human and animal surveillance",
      "Protect people with occupational exposure",
      "Investigate and characterize human infections",
    ],
    url: "https://www.who.int/news-room/fact-sheets/detail/influenza-(avian-and-other-zoonotic)",
  },
  {
    name: "Dengue",
    family: "Vector-borne viral disease",
    route: "Bites from infected mosquitoes",
    summary:
      "Dengue is a viral infection transmitted by infected mosquitoes. It is common in tropical and subtropical climates, particularly in urban and semi-urban areas.",
    priorities: [
      "Mosquito surveillance and vector control",
      "Reduce mosquito breeding opportunities",
      "Early detection and access to appropriate care",
    ],
    url: "https://www.who.int/health-topics/dengue-and-severe-dengue",
  },
  {
    name: "Cholera",
    family: "Bacterial disease",
    route: "Contaminated food or water",
    summary:
      "Cholera is an acute diarrhoeal infection caused by consuming food or water contaminated with Vibrio cholerae. Safe water and sanitation are central to prevention.",
    priorities: [
      "Safe water, sanitation and hygiene",
      "Early surveillance and rapid response",
      "Access to treatment and oral cholera vaccines",
    ],
    url: "https://www.who.int/news-room/fact-sheets/detail/cholera",
  },
  {
    name: "Measles",
    family: "Viral disease",
    route: "Airborne transmission",
    summary:
      "Measles is a highly contagious airborne viral disease. It can cause serious complications and is preventable through vaccination.",
    priorities: [
      "Routine immunization and closing immunity gaps",
      "Prompt case detection and surveillance",
      "Outbreak response guided by health authorities",
    ],
    url: "https://www.who.int/news-room/fact-sheets/detail/measles",
  },
];
