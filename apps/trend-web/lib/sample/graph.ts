/* 예시 '콘텐츠 → 나라별 파생 항목'. 시험판 결과(Squid Game.json)를 GET /graph/content/{key} 모양으로 옮긴 것 — 나라마다 최대 15개,
   나무위키 분류는 한국 칸에 합쳤다. */
import type { GraphContent, GraphContentSummary } from "../types";

export const SAMPLE_GRAPH_CONTENTS: GraphContentSummary[] = [{"key": "Squid Game", "name": "Squid Game", "qid": "Q106582931", "labels": {"en": "Squid Game", "zh": "魷魚遊戲", "ko": "오징어 게임", "vi": "Trò chơi con mực", "ja": "イカゲーム", "th": "สควิดเกม เล่นลุ้นตาย", "id": "Squid Game"}, "items": 66, "in_dictionary": 1}];

export const SAMPLE_GRAPH: Record<string, GraphContent> = {
  "Squid Game": {
    "content": {
      "key": "Squid Game",
      "name": "Squid Game",
      "qid": "Q106582931",
      "labels": {
        "en": "Squid Game",
        "zh": "魷魚遊戲",
        "ko": "오징어 게임",
        "vi": "Trò chơi con mực",
        "ja": "イカゲーム",
        "th": "สควิดเกม เล่นลุ้นตาย",
        "id": "Squid Game"
      }
    },
    "countries": [
      {
        "region": "KR",
        "lang": "ko",
        "label": "오징어 게임",
        "sources": [
          "분류:오징어 게임",
          "나무위키 분류:오징어 게임"
        ],
        "items": [
          {
            "title": "오징어 게임",
            "term_id": "t_28634695a6",
            "status": "verified",
            "definition": "넷플릭스 오리지널 서바이벌 리얼리티쇼의 이름으로 언급되며, 인터넷 밈이나 패러디 영상 등에서 사용되는 콘텐츠.",
            "kind": "wiki",
            "url": "https://ko.wikipedia.org/wiki/%EC%98%A4%EC%A7%95%EC%96%B4_%EA%B2%8C%EC%9E%84",
            "evidence": ""
          },
          {
            "title": "둥글게 둥글게",
            "term_id": "t_2c213eb51a",
            "status": "needs_review",
            "definition": null,
            "kind": "wiki",
            "url": "https://namu.wiki/w/%EB%91%A5%EA%B8%80%EA%B2%8C%20%EB%91%A5%EA%B8%80%EA%B2%8C",
            "evidence": ""
          },
          {
            "title": "오징어 게임(시즌 1)",
            "term_id": "t_28634695a6",
            "status": "verified",
            "definition": "넷플릭스 오리지널 서바이벌 리얼리티쇼의 이름으로 언급되며, 인터넷 밈이나 패러디 영상 등에서 사용되는 콘텐츠.",
            "kind": "wiki",
            "url": "https://namu.wiki/w/%EC%98%A4%EC%A7%95%EC%96%B4%20%EA%B2%8C%EC%9E%84%28%EC%8B%9C%EC%A6%8C%201%29",
            "evidence": ""
          },
          {
            "title": "오징어 게임(시즌 2)",
            "term_id": "t_28634695a6",
            "status": "verified",
            "definition": "넷플릭스 오리지널 서바이벌 리얼리티쇼의 이름으로 언급되며, 인터넷 밈이나 패러디 영상 등에서 사용되는 콘텐츠.",
            "kind": "wiki",
            "url": "https://namu.wiki/w/%EC%98%A4%EC%A7%95%EC%96%B4%20%EA%B2%8C%EC%9E%84%28%EC%8B%9C%EC%A6%8C%202%29",
            "evidence": ""
          },
          {
            "title": "오징어 게임(시즌 3)",
            "term_id": "t_28634695a6",
            "status": "verified",
            "definition": "넷플릭스 오리지널 서바이벌 리얼리티쇼의 이름으로 언급되며, 인터넷 밈이나 패러디 영상 등에서 사용되는 콘텐츠.",
            "kind": "wiki",
            "url": "https://namu.wiki/w/%EC%98%A4%EC%A7%95%EC%96%B4%20%EA%B2%8C%EC%9E%84%28%EC%8B%9C%EC%A6%8C%203%29",
            "evidence": ""
          },
          {
            "title": "오징어 게임(오징어 게임)",
            "term_id": "t_28634695a6",
            "status": "verified",
            "definition": "넷플릭스 오리지널 서바이벌 리얼리티쇼의 이름으로 언급되며, 인터넷 밈이나 패러디 영상 등에서 사용되는 콘텐츠.",
            "kind": "wiki",
            "url": "https://namu.wiki/w/%EC%98%A4%EC%A7%95%EC%96%B4%20%EA%B2%8C%EC%9E%84%28%EC%98%A4%EC%A7%95%EC%96%B4%20%EA%B2%8C%EC%9E%84%29",
            "evidence": ""
          },
          {
            "title": "$456,000를 걸고 실제 오징어 게임을 해보았습니다!",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://ko.wikipedia.org/wiki/%24456%2C000%EB%A5%BC_%EA%B1%B8%EA%B3%A0_%EC%8B%A4%EC%A0%9C_%EC%98%A4%EC%A7%95%EC%96%B4_%EA%B2%8C%EC%9E%84%EC%9D%84_%ED%95%B4%EB%B3%B4%EC%95%98%EC%8A%B5%EB%8B%88%EB%8B%A4%21",
            "evidence": ""
          },
          {
            "title": "비스트 게임",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://ko.wikipedia.org/wiki/%EB%B9%84%EC%8A%A4%ED%8A%B8_%EA%B2%8C%EC%9E%84",
            "evidence": ""
          },
          {
            "title": "오징어 게임 시즌 1",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://ko.wikipedia.org/wiki/%EC%98%A4%EC%A7%95%EC%96%B4_%EA%B2%8C%EC%9E%84_%EC%8B%9C%EC%A6%8C_1",
            "evidence": ""
          },
          {
            "title": "오징어 게임 시즌 2",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://ko.wikipedia.org/wiki/%EC%98%A4%EC%A7%95%EC%96%B4_%EA%B2%8C%EC%9E%84_%EC%8B%9C%EC%A6%8C_2",
            "evidence": ""
          },
          {
            "title": "오징어 게임 시즌 3",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://ko.wikipedia.org/wiki/%EC%98%A4%EC%A7%95%EC%96%B4_%EA%B2%8C%EC%9E%84_%EC%8B%9C%EC%A6%8C_3",
            "evidence": ""
          },
          {
            "title": "오징어 게임: 더 챌린지",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://ko.wikipedia.org/wiki/%EC%98%A4%EC%A7%95%EC%96%B4_%EA%B2%8C%EC%9E%84%3A_%EB%8D%94_%EC%B1%8C%EB%A6%B0%EC%A7%80",
            "evidence": ""
          },
          {
            "title": "황동혁",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://ko.wikipedia.org/wiki/%ED%99%A9%EB%8F%99%ED%98%81",
            "evidence": ""
          },
          {
            "title": "5인 6각 근대 5종 경기",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://namu.wiki/w/5%EC%9D%B8%206%EA%B0%81%20%EA%B7%BC%EB%8C%80%205%EC%A2%85%20%EA%B2%BD%EA%B8%B0",
            "evidence": ""
          },
          {
            "title": "Squid Game: The Final Games",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://namu.wiki/w/Squid%20Game%3A%20The%20Final%20Games",
            "evidence": ""
          }
        ]
      },
      {
        "region": "US",
        "lang": "en",
        "label": "Squid Game",
        "sources": [
          "Category:Squid Game"
        ],
        "items": [
          {
            "title": "$456,000 Squid Game in Real Life!",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/%24456%2C000_Squid_Game_in_Real_Life%21",
            "evidence": ""
          },
          {
            "title": "001 (Squid Game)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/001_%28Squid_Game%29",
            "evidence": ""
          },
          {
            "title": "2021 Squid Game cryptocurrency scam",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/2021_Squid_Game_cryptocurrency_scam",
            "evidence": ""
          },
          {
            "title": "222 (Squid Game)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/222_%28Squid_Game%29",
            "evidence": ""
          },
          {
            "title": "50 YouTubers Fight for $1,000,000",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/50_YouTubers_Fight_for_%241%2C000%2C000",
            "evidence": ""
          },
          {
            "title": "A Fair World",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/A_Fair_World",
            "evidence": ""
          },
          {
            "title": "A Fair World (Squid Game)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/A_Fair_World_%28Squid_Game%29",
            "evidence": ""
          },
          {
            "title": "Ali Abdul",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/Ali_Abdul",
            "evidence": ""
          },
          {
            "title": "Beast Games",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/Beast_Games",
            "evidence": ""
          },
          {
            "title": "Beast Games season 1",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/Beast_Games_season_1",
            "evidence": ""
          },
          {
            "title": "Beast Games season 2",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/Beast_Games_season_2",
            "evidence": ""
          },
          {
            "title": "Bread and Lottery",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/Bread_and_Lottery",
            "evidence": ""
          },
          {
            "title": "Cho Hyun-ju",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/Cho_Hyun-ju",
            "evidence": ""
          },
          {
            "title": "Cho Sang-woo (Squid Game)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/Cho_Sang-woo_%28Squid_Game%29",
            "evidence": ""
          },
          {
            "title": "Crab Game",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://en.wikipedia.org/wiki/Crab_Game",
            "evidence": ""
          }
        ]
      },
      {
        "region": "JP",
        "lang": "ja",
        "label": "イカゲーム",
        "sources": [
          "Category:イカゲーム"
        ],
        "items": []
      },
      {
        "region": "TW",
        "lang": "zh",
        "label": "魷魚遊戲",
        "sources": [
          "Category:魷魚遊戲"
        ],
        "items": [
          {
            "title": "墨魚遊戲 (第二輯)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E5%A2%A8%E9%AD%9A%E9%81%8A%E6%88%B2_%28%E7%AC%AC%E4%BA%8C%E8%BC%AF%29",
            "evidence": ""
          },
          {
            "title": "現實版魷魚遊戲，堅持到最後贏得456,000美元！",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E7%8F%BE%E5%AF%A6%E7%89%88%E9%AD%B7%E9%AD%9A%E9%81%8A%E6%88%B2%EF%BC%8C%E5%A0%85%E6%8C%81%E5%88%B0%E6%9C%80%E5%BE%8C%E8%B4%8F%E5%BE%97456%2C000%E7%BE%8E%E5%85%83%EF%BC%81",
            "evidence": ""
          },
          {
            "title": "野獸遊戲",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E9%87%8E%E7%8D%B8%E9%81%8A%E6%88%B2",
            "evidence": ""
          },
          {
            "title": "魷魚遊戲 (第一季)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E9%AD%B7%E9%AD%9A%E9%81%8A%E6%88%B2_%28%E7%AC%AC%E4%B8%80%E5%AD%A3%29",
            "evidence": ""
          },
          {
            "title": "魷魚遊戲2",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E9%AD%B7%E9%AD%9A%E9%81%8A%E6%88%B22",
            "evidence": ""
          },
          {
            "title": "魷魚遊戲3",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E9%AD%B7%E9%AD%9A%E9%81%8A%E6%88%B23",
            "evidence": ""
          },
          {
            "title": "魷魚遊戲獲獎與提名列表",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E9%AD%B7%E9%AD%9A%E9%81%8A%E6%88%B2%E7%8D%B2%E7%8D%8E%E8%88%87%E6%8F%90%E5%90%8D%E5%88%97%E8%A1%A8",
            "evidence": ""
          },
          {
            "title": "魷魚遊戲系列",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E9%AD%B7%E9%AD%9A%E9%81%8A%E6%88%B2%E7%B3%BB%E5%88%97",
            "evidence": ""
          },
          {
            "title": "魷魚遊戲：真人挑戰賽",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://zh.wikipedia.org/wiki/%E9%AD%B7%E9%AD%9A%E9%81%8A%E6%88%B2%EF%BC%9A%E7%9C%9F%E4%BA%BA%E6%8C%91%E6%88%B0%E8%B3%BD",
            "evidence": ""
          }
        ]
      },
      {
        "region": "TH",
        "lang": "th",
        "label": "สควิดเกม เล่นลุ้นตาย",
        "sources": [
          "Category:สควิดเกม เล่นลุ้นตาย"
        ],
        "items": [
          {
            "title": "ชุดโกโกวา",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%8A%E0%B8%B8%E0%B8%94%E0%B9%82%E0%B8%81%E0%B9%82%E0%B8%81%E0%B8%A7%E0%B8%B2",
            "evidence": ""
          },
          {
            "title": "ซ็อง กี-ฮุน",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%8B%E0%B9%87%E0%B8%AD%E0%B8%87_%E0%B8%81%E0%B8%B5-%E0%B8%AE%E0%B8%B8%E0%B8%99",
            "evidence": ""
          },
          {
            "title": "ธานอส (สควิดเกม เล่นลุ้นตาย)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%98%E0%B8%B2%E0%B8%99%E0%B8%AD%E0%B8%AA_%28%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%A5%E0%B9%88%E0%B8%99%E0%B8%A5%E0%B8%B8%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%B2%E0%B8%A2%29",
            "evidence": ""
          },
          {
            "title": "ผู้สรรหา (สควิดเกม เล่นลุ้นตาย)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%9C%E0%B8%B9%E0%B9%89%E0%B8%AA%E0%B8%A3%E0%B8%A3%E0%B8%AB%E0%B8%B2_%28%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%A5%E0%B9%88%E0%B8%99%E0%B8%A5%E0%B8%B8%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%B2%E0%B8%A2%29",
            "evidence": ""
          },
          {
            "title": "ฟรอนต์แมน (สควิดเกม เล่นลุ้นตาย)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%9F%E0%B8%A3%E0%B8%AD%E0%B8%99%E0%B8%95%E0%B9%8C%E0%B9%81%E0%B8%A1%E0%B8%99_%28%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%A5%E0%B9%88%E0%B8%99%E0%B8%A5%E0%B8%B8%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%B2%E0%B8%A2%29",
            "evidence": ""
          },
          {
            "title": "รายชื่อตัวละครในสควิดเกม เล่นลุ้นตาย",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%A3%E0%B8%B2%E0%B8%A2%E0%B8%8A%E0%B8%B7%E0%B9%88%E0%B8%AD%E0%B8%95%E0%B8%B1%E0%B8%A7%E0%B8%A5%E0%B8%B0%E0%B8%84%E0%B8%A3%E0%B9%83%E0%B8%99%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%A5%E0%B9%88%E0%B8%99%E0%B8%A5%E0%B8%B8%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%B2%E0%B8%A2",
            "evidence": ""
          },
          {
            "title": "วีไอพี (สควิดเกม เล่นลุ้นตาย)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%A7%E0%B8%B5%E0%B9%84%E0%B8%AD%E0%B8%9E%E0%B8%B5_%28%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%A5%E0%B9%88%E0%B8%99%E0%B8%A5%E0%B8%B8%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%B2%E0%B8%A2%29",
            "evidence": ""
          },
          {
            "title": "สควิดเกม เดอะ ชาเลนจ์",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%94%E0%B8%AD%E0%B8%B0_%E0%B8%8A%E0%B8%B2%E0%B9%80%E0%B8%A5%E0%B8%99%E0%B8%88%E0%B9%8C",
            "evidence": ""
          },
          {
            "title": "สควิดเกม เล่นลุ้นตาย",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%A5%E0%B9%88%E0%B8%99%E0%B8%A5%E0%B8%B8%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%B2%E0%B8%A2",
            "evidence": ""
          },
          {
            "title": "สควิดเกม เล่นลุ้นตาย ฤดูกาลที่ 2",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%A5%E0%B9%88%E0%B8%99%E0%B8%A5%E0%B8%B8%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%B2%E0%B8%A2_%E0%B8%A4%E0%B8%94%E0%B8%B9%E0%B8%81%E0%B8%B2%E0%B8%A5%E0%B8%97%E0%B8%B5%E0%B9%88_2",
            "evidence": ""
          },
          {
            "title": "สควิดเกม เล่นลุ้นตาย ฤดูกาลที่ 3",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1_%E0%B9%80%E0%B8%A5%E0%B9%88%E0%B8%99%E0%B8%A5%E0%B8%B8%E0%B9%89%E0%B8%99%E0%B8%95%E0%B8%B2%E0%B8%A2_%E0%B8%A4%E0%B8%94%E0%B8%B9%E0%B8%81%E0%B8%B2%E0%B8%A5%E0%B8%97%E0%B8%B5%E0%B9%88_3",
            "evidence": ""
          },
          {
            "title": "สควิดเกมในชีวิตจริงมูลค่า 456,000 เหรียญ!",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B8%AA%E0%B8%84%E0%B8%A7%E0%B8%B4%E0%B8%94%E0%B9%80%E0%B8%81%E0%B8%A1%E0%B9%83%E0%B8%99%E0%B8%8A%E0%B8%B5%E0%B8%A7%E0%B8%B4%E0%B8%95%E0%B8%88%E0%B8%A3%E0%B8%B4%E0%B8%87%E0%B8%A1%E0%B8%B9%E0%B8%A5%E0%B8%84%E0%B9%88%E0%B8%B2_456%2C000_%E0%B9%80%E0%B8%AB%E0%B8%A3%E0%B8%B5%E0%B8%A2%E0%B8%8D%21",
            "evidence": ""
          },
          {
            "title": "แครบเกม",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B9%81%E0%B8%84%E0%B8%A3%E0%B8%9A%E0%B9%80%E0%B8%81%E0%B8%A1",
            "evidence": ""
          },
          {
            "title": "โช ฮย็อน-จู",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://th.wikipedia.org/wiki/%E0%B9%82%E0%B8%8A_%E0%B8%AE%E0%B8%A2%E0%B9%87%E0%B8%AD%E0%B8%99-%E0%B8%88%E0%B8%B9",
            "evidence": ""
          }
        ]
      },
      {
        "region": "VN",
        "lang": "vi",
        "label": "Trò chơi con mực",
        "sources": [
          "Category:Trò chơi con mực"
        ],
        "items": [
          {
            "title": "$456,000 Squid Game in Real Life!",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://vi.wikipedia.org/wiki/%24456%2C000_Squid_Game_in_Real_Life%21",
            "evidence": ""
          },
          {
            "title": "Danh sách giải thưởng và đề cử của Trò chơi con mực",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://vi.wikipedia.org/wiki/Danh_s%C3%A1ch_gi%E1%BA%A3i_th%C6%B0%E1%BB%9Fng_v%C3%A0_%C4%91%E1%BB%81_c%E1%BB%AD_c%E1%BB%A7a_Tr%C3%B2_ch%C6%A1i_con_m%E1%BB%B1c",
            "evidence": ""
          },
          {
            "title": "Hwang Dong-hyuk",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://vi.wikipedia.org/wiki/Hwang_Dong-hyuk",
            "evidence": ""
          },
          {
            "title": "Trò chơi con mực",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://vi.wikipedia.org/wiki/Tr%C3%B2_ch%C6%A1i_con_m%E1%BB%B1c",
            "evidence": ""
          },
          {
            "title": "Trò chơi con mực (mùa 1)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://vi.wikipedia.org/wiki/Tr%C3%B2_ch%C6%A1i_con_m%E1%BB%B1c_%28m%C3%B9a_1%29",
            "evidence": ""
          },
          {
            "title": "Trò chơi con mực (mùa 2)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://vi.wikipedia.org/wiki/Tr%C3%B2_ch%C6%A1i_con_m%E1%BB%B1c_%28m%C3%B9a_2%29",
            "evidence": ""
          },
          {
            "title": "Trò chơi con mực (mùa 3)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://vi.wikipedia.org/wiki/Tr%C3%B2_ch%C6%A1i_con_m%E1%BB%B1c_%28m%C3%B9a_3%29",
            "evidence": ""
          }
        ]
      },
      {
        "region": "ID",
        "lang": "id",
        "label": "Squid Game",
        "sources": [
          "Category:Squid Game"
        ],
        "items": [
          {
            "title": "Squid Game",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://id.wikipedia.org/wiki/Squid_Game",
            "evidence": ""
          },
          {
            "title": "Squid Game (musim 1)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://id.wikipedia.org/wiki/Squid_Game_%28musim_1%29",
            "evidence": ""
          },
          {
            "title": "Squid Game (musim 2)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://id.wikipedia.org/wiki/Squid_Game_%28musim_2%29",
            "evidence": ""
          },
          {
            "title": "Squid Game (musim 3)",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://id.wikipedia.org/wiki/Squid_Game_%28musim_3%29",
            "evidence": ""
          },
          {
            "title": "Squid Game Berhadiah $456,000 di Kehidupan Nyata!",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://id.wikipedia.org/wiki/Squid_Game_Berhadiah_%24456%2C000_di_Kehidupan_Nyata%21",
            "evidence": ""
          },
          {
            "title": "Squid Game: The Challenge",
            "term_id": null,
            "status": null,
            "definition": null,
            "kind": "wiki",
            "url": "https://id.wikipedia.org/wiki/Squid_Game%3A_The_Challenge",
            "evidence": ""
          }
        ]
      }
    ],
    "updated_at": "2026-10-01T00:00:00Z"
  },
};
