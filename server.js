const express = require('express');
const cors = require('cors');
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 8765;

app.use(cors());

// ─── Utils ────────────────────────────────────────────────────────
const getTodayTH = () => {
  const d = new Date();
  const months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"];
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear() + 543}`;
};

// ─── Scraper: Thai Gov ────────────────────────────────────────────────
async function fetchThaiGov() {
  try {
    const { data } = await axios.get('https://lotto.sanook.com/', { timeout: 10000 });
    const $ = cheerio.load(data);
    
    let prize1 = null;
    let last2 = null;
    let dateStr = getTodayTH();

    // Prize 1
    const prize1El = $('.lotto-prize-first .number, .lottery-result__prize-first span.number').first().text();
    if (prize1El) {
      const match = prize1El.match(/\d{6}/);
      if (match) prize1 = match[0];
    } else {
      // Fallback
      const ps = $('p').text();
      const firstMatches = ps.match(/\b\d{6}\b/g);
      if (firstMatches) prize1 = firstMatches[0];
    }

    // Last 2
    const last2El = $('.lotto-prize-last2 .number, .lottery-result__last2 span.number').first().text().trim();
    if (last2El) {
      const match = last2El.match(/\d{2}/);
      if (match) last2 = match[0];
    }

    // 3 Front
    const front3 = [];
    $('.lotto-prize-front3 span.number, .lottery-result__front3 span.number, strong.number').each((i, el) => {
      const parentClass = $(el).parent().attr('class') || '';
      if (parentClass.includes('front3') || $(el).closest('.lotto-prize-front3').length) {
        const text = $(el).text().trim();
        const match = text.match(/\d{3}/);
        if (match) front3.push(match[0]);
      }
    });

    // 3 Back
    const back3 = [];
    $('.lotto-prize-back3 span.number, .lottery-result__back3 span.number, strong.number').each((i, el) => {
      const parentClass = $(el).parent().attr('class') || '';
      if (parentClass.includes('back3') || $(el).closest('.lotto-prize-back3').length) {
        const text = $(el).text().trim();
        const match = text.match(/\d{3}/);
        if (match) back3.push(match[0]);
      }
    });

    // Date
    const dateEl = $('.lotto-date, .lottery-result__date, time').first().text().trim();
    if (dateEl) dateStr = dateEl;

    // Fallback regex scan if Cheerio specific selectors missed
    if (front3.length === 0 || back3.length === 0) {
      const allText = $('body').text().replace(/\s+/g, ' ');
      // Try to find the list of 3 digit numbers near keywords
      const frontMatch = allText.match(/3 ตัวหน้า.*?(\d{3}).*?(\d{3})/);
      if (frontMatch) {
         if (front3.length === 0) { front3.push(frontMatch[1], frontMatch[2]); }
      }
      const backMatch = allText.match(/3 ตัวหลัง.*?(\d{3}).*?(\d{3})/);
      if (backMatch) {
         if (back3.length === 0) { back3.push(backMatch[1], backMatch[2]); }
      }
    }

    if (prize1) {
      return {
        source: 'sanook.com',
        available: true,
        prize1,
        last2: last2 || '—',
        front3: front3.length ? front3 : ['???', '???'],
        back3: back3.length ? back3 : ['???', '???'],
        date: dateStr,
        fetched_at: new Date().toISOString()
      };
    }
  } catch (err) {
    console.error("ThaiGov Scrape Error:", err.message);
  }

  // Fallback Data
  return {
    source: 'fallback',
    available: false,
    prize1: '481625',
    last2: '25',
    front3: ['194', '859'],
    back3: ['012', '936'],
    date: '1 เมษายน 2569',
    fetched_at: new Date().toISOString(),
    note: "ไม่สามารถดึงข้อมูลจริงได้ กำลังแสดงข้อมูลสำรอง"
  };
}

// ─── Scraper: Lao ────────────────────────────────────────────────
async function fetchLao() {
  try {
    const { data } = await axios.get('https://laohuay.com/', { timeout: 10000 });
    const match = data.match(/\b\d{4}\b/);
    
    if (match) {
      const prize_4d = match[0];
      return {
        source: 'laohuay.com',
        available: true,
        num4: prize_4d,
        num3: prize_4d.substring(1),
        num2: prize_4d.substring(2),
        top: prize_4d,
        date: getTodayTH(),
        fetched_at: new Date().toISOString()
      };
    }
  } catch (err) {
    console.error("Lao Scrape Error:", err.message);
  }

  return {
    source: 'fallback',
    available: false,
    num4: '8362',
    num3: '362',
    num2: '62',
    date: getTodayTH(),
    fetched_at: new Date().toISOString()
  };
}

// ─── Scraper: Hanoi ────────────────────────────────────────────────
async function fetchHanoi() {
  try {
    const { data } = await axios.get('https://www.check-huay.com/hanoi', { timeout: 10000 });
    const match = data.match(/\b\d{5}\b/);
    
    if (match) {
      const g1 = match[0];
      return {
        source: 'check-huay.com',
        available: true,
        g1,
        back3: g1.substring(2),
        back2: g1.substring(3),
        date: getTodayTH(),
        fetched_at: new Date().toISOString()
      };
    }
  } catch (err) {
    console.error("Hanoi Scrape Error:", err.message);
  }

  return {
    source: 'fallback',
    available: false,
    g1: '81742',
    back3: '742',
    back2: '42',
    date: getTodayTH(),
    fetched_at: new Date().toISOString()
  };
}

// ─── Endpoints ────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.json({ status: 'ok', service: 'LottoAI Pro API (Node)' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.get('/api/thai-gov', async (req, res) => {
  const result = await fetchThaiGov();
  res.json(result);
});

app.get('/api/lao', async (req, res) => {
  const result = await fetchLao();
  res.json(result);
});

app.get('/api/hanoi', async (req, res) => {
  const result = await fetchHanoi();
  res.json(result);
});

app.get('/api/all', async (req, res) => {
  const [thai_gov, lao, hanoi] = await Promise.all([
    fetchThaiGov(),
    fetchLao(),
    fetchHanoi()
  ]);
  
  res.json({ thai_gov, lao, hanoi });
});

app.listen(PORT, () => {
  console.log(`===================================================`);
  console.log(`  LottoAI Pro — Backend Node API Server`);
  console.log(`===================================================`);
  console.log(`🟢 Server running at http://127.0.0.1:${PORT}`);
  console.log(`\nEndpoints:`);
  console.log(`  GET /api/thai-gov`);
  console.log(`  GET /api/lao`);
  console.log(`  GET /api/hanoi`);
  console.log(`  GET /api/all`);
  console.log(`===================================================`);
});
