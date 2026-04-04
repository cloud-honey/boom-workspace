#!/usr/bin/env node

/**
 * 붐엘 텔레그램 봇 - MLX 최적화 전용 에이전트
 * macOS 전용, MLX 성능 테스트 결과 실시간 전송
 */

const { Telegraf } = require('telegraf');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// 환경 변수에서 API 토큰 로드
const BOT_TOKEN = process.env.BOOML_BOT_TOKEN || "8592906266:AAGA326kDs1pNXbVRWbwtWxIUR3n9VkKQYE";
const MASTER_CHAT_ID = 47980209; // 마스터 텔레그램 ID (숫자로)

console.log(`🔧 BOT_TOKEN 확인: ${BOT_TOKEN ? '설정됨' : '설정 안됨'}`);
console.log(`🔧 MASTER_CHAT_ID: ${MASTER_CHAT_ID}`);

if (!BOT_TOKEN) {
  console.error('❌ BOOML_BOT_TOKEN 환경 변수가 설정되지 않았습니다.');
  console.error('BotFather에서 봇을 생성하고 토큰을 설정하세요.');
  console.error('현재 .env 파일 내용:');
  try {
    const envContent = fs.readFileSync(path.join(__dirname, '.env'), 'utf8');
    console.error(envContent);
  } catch (e) {
    console.error('.env 파일 읽기 실패:', e.message);
  }
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

// MLX 성능 테스트 함수
async function runMLXBenchmark() {
  return new Promise((resolve, reject) => {
    const benchmarkScript = path.join(__dirname, 'mlx-benchmark.py');
    
    exec(`python3 ${benchmarkScript}`, (error, stdout, stderr) => {
      if (error) {
        reject(`MLX 벤치마크 실패: ${stderr}`);
      } else {
        resolve(stdout);
      }
    });
  });
}

// Ollama vs MLX 비교 함수
async function compareOllamaMLX() {
  return new Promise((resolve, reject) => {
    const compareScript = path.join(__dirname, 'compare-models.py');
    
    exec(`python3 ${compareScript}`, (error, stdout, stderr) => {
      if (error) {
        reject(`모델 비교 실패: ${stderr}`);
      } else {
        resolve(stdout);
      }
    });
  });
}

// MLX 모델 로드 상태 확인
async function checkMLXStatus() {
  return new Promise((resolve, reject) => {
    exec('python3 -c "import mlx.core as mx; print(\'✅ MLX 설치됨\')"', (error, stdout, stderr) => {
      if (error) {
        resolve('❌ MLX 설치되지 않음');
      } else {
        resolve('✅ MLX 설치됨');
      }
    });
  });
}

// 명령어 처리
bot.command('start', (ctx) => {
  ctx.reply(`🤖 붐엘 텔레그램 봇에 오신 것을 환영합니다!
  
명령어:
/status - MLX 상태 확인
/benchmark - MLX 성능 테스트 실행
/compare - Ollama vs MLX 비교
/help - 도움말`);
});

bot.command('status', async (ctx) => {
  ctx.reply('MLX 상태 확인 중...');
  
  try {
    const mlxStatus = await checkMLXStatus();
    const ollamaStatus = await new Promise((resolve) => {
      exec('ollama ps', (error, stdout) => {
        if (error) {
          resolve('❌ Ollama 실행 중 아님');
        } else {
          resolve('✅ Ollama 실행 중');
        }
      });
    });
    
    ctx.reply(`📊 시스템 상태:
${mlxStatus}
${ollamaStatus}
    
💻 macOS M4 Pro (45GB VRAM)
🎯 붐엘: MLX 최적화 전용 에이전트`);
  } catch (error) {
    ctx.reply(`❌ 상태 확인 실패: ${error}`);
  }
});

bot.command('benchmark', async (ctx) => {
  ctx.reply('🚀 MLX 성능 벤치마크 실행 중...');
  
  try {
    const result = await runMLXBenchmark();
    ctx.reply(`📈 MLX 벤치마크 결과:
${result}`);
    
    // 마스터에게도 결과 전송
    if (ctx.chat.id.toString() !== MASTER_CHAT_ID) {
      bot.telegram.sendMessage(MASTER_CHAT_ID, `📊 붐엘 벤치마크 결과:\n${result}`);
    }
  } catch (error) {
    ctx.reply(`❌ 벤치마크 실패: ${error}`);
  }
});

bot.command('compare', async (ctx) => {
  ctx.reply('⚖️ Ollama vs MLX 비교 분석 중...');
  
  try {
    const result = await compareOllamaMLX();
    ctx.reply(`📊 모델 비교 결과:
${result}`);
  } catch (error) {
    ctx.reply(`❌ 비교 실패: ${error}`);
  }
});

bot.command('help', (ctx) => {
  ctx.reply(`🛠️ 붐엘 봇 도움말

붐엘은 macOS M4 Pro에서 MLX 프레임워크를 사용한 고속 로컬 LLM 최적화 전용 에이전트입니다.

📋 주요 기능:
• MLX 성능 벤치마크
• Ollama vs MLX 속도 비교
• macOS Metal 가속 최적화
• 토큰 속도 모니터링

🔧 명령어:
/status - 시스템 상태 확인
/benchmark - MLX 성능 테스트
/compare - Ollama와 MLX 비교
/help - 이 도움말

⚡ 붐엘 특징:
• macOS 전용 (Metal 가속)
• MLX 프레임워크 최적화
• 영어 프롬프트 전용
• 실시간 성능 모니터링`);
});

// 모든 텍스트 메시지에 응답
bot.on('text', (ctx) => {
  const message = ctx.message.text;
  
  // 마스터 메시지인 경우
  if (ctx.chat.id === MASTER_CHAT_ID) {
    ctx.reply(`🔧 붐엘이 메시지를 받았습니다: "${message}"
    
MLX 최적화 작업을 진행하시겠습니까?`);
  } else {
    ctx.reply('안녕하세요! 저는 붐엘 봇입니다. /help 명령어로 사용법을 확인하세요.');
  }
});

// 에러 처리
bot.catch((err, ctx) => {
  console.error(`봇 에러: ${err}`);
  ctx.reply('❌ 봇 처리 중 오류가 발생했습니다.');
});

// 봇 시작
console.log('🤖 붐엘 텔레그램 봇 시작 중...');

// 먼저 봇 정보 확인
bot.telegram.getMe().then(me => {
  console.log(`✅ 봇 정보 확인: @${me.username} (${me.first_name})`);
  
  // 봇 시작
  return bot.launch();
}).then(() => {
  console.log('✅ 붐엘 봇이 시작되었습니다!');
  
  // 마스터에게 시작 알림
  return bot.telegram.sendMessage(MASTER_CHAT_ID, 
    '🚀 붐엘 텔레그램 봇이 시작되었습니다!\n\n' +
    'MLX 최적화 에이전트가 준비되었습니다. /help 명령어로 사용법을 확인하세요.'
  );
}).then(() => {
  console.log('✅ 마스터에게 시작 알림 전송 완료');
  console.log('✅ 봇이 정상적으로 실행 중입니다.');
  console.log('✅ 텔레그램에서 @boomllm_bot 으로 접속하세요.');
}).catch(err => {
  console.error('❌ 봇 시작 실패:', err.message);
  console.error('상세 에러:', err);
  process.exit(1);
});

// 종료 시그널 처리
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));