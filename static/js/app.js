document.addEventListener('DOMContentLoaded', () => {
  // DOM 요소 선택
  const form = document.getElementById('recipeForm');
  const ingredientsInput = document.getElementById('ingredients');
  const clearIngredientsBtn = document.getElementById('clearIngredientsBtn');
  const randomRecipeBtn = document.getElementById('randomRecipeBtn');
  const ingredientChips = document.querySelectorAll('.ingredient-chip');
  const generateBtn = document.getElementById('generateBtn');
  const loadingSection = document.getElementById('loadingSection');
  const recipeSelectionSection = document.getElementById('recipeSelectionSection');
  const recipeTabs = document.getElementById('recipeTabs');
  const resultSection = document.getElementById('resultSection');
  const errorAlert = document.getElementById('errorAlert');
  const errorMessage = document.getElementById('errorMessage');
  const copyBtn = document.getElementById('copyBtn');
  const downloadBtn = document.getElementById('downloadBtn');
  const printBtn = document.getElementById('printBtn');
  const bookmarkBtn = document.getElementById('bookmarkBtn');
  const openBookmarksBtn = document.getElementById('openBookmarksBtn');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const bookmarkDrawer = document.getElementById('bookmarkDrawer');
  const bookmarkList = document.getElementById('bookmarkList');
  const bookmarkCountBadge = document.getElementById('bookmarkCountBadge');

  // 상태 관리 변수
  let currentRecipeList = [];
  let activeRecipeIndex = 0;
  let currentRecipeData = null;
  const STORAGE_KEY = 'ai_recipe_studio_bookmarks';

  // 1. 초기화 및 북마크 뱃지 설정
  updateBookmarkBadge();
  syncChipsWithInput();

  // 2. 인기 식재료 태그 칩 클릭 핸들러
  ingredientChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const name = chip.getAttribute('data-name');
      let currentVal = ingredientsInput.value.trim();
      let items = currentVal ? currentVal.split(',').map(s => s.trim()).filter(Boolean) : [];

      const existsIndex = items.findIndex(item => item.includes(name) || name.includes(item));

      if (existsIndex >= 0) {
        // 이미 있으면 제거 (토글)
        items.splice(existsIndex, 1);
        chip.classList.remove('chip-active');
      } else {
        // 없으면 추가
        items.push(name);
        chip.classList.add('chip-active');
      }

      ingredientsInput.value = items.join(', ');
      toggleClearButton();
    });
  });

  // 직접 텍스트 입력 시 칩 상태 및 비우기 버튼 동기화
  ingredientsInput.addEventListener('input', () => {
    syncChipsWithInput();
    toggleClearButton();
  });

  function syncChipsWithInput() {
    const text = ingredientsInput.value.trim();
    ingredientChips.forEach(chip => {
      const name = chip.getAttribute('data-name');
      if (text.includes(name)) {
        chip.classList.add('chip-active');
      } else {
        chip.classList.remove('chip-active');
      }
    });
  }

  function toggleClearButton() {
    if (ingredientsInput.value.trim()) {
      clearIngredientsBtn.classList.remove('hidden');
    } else {
      clearIngredientsBtn.classList.add('hidden');
    }
  }

  // 재료 전체 비우기 버튼
  clearIngredientsBtn.addEventListener('click', () => {
    ingredientsInput.value = '';
    syncChipsWithInput();
    toggleClearButton();
    ingredientsInput.focus();
  });

  // 3. "오늘 뭐 먹지? 랜덤 추천 (Surprise Me)" 큐레이션 세트
  const randomCombos = [
    {
      ingredients: '감자 2개, 양파 1개, 스팸 1캔, 계란',
      servings: '2인분',
      time: '20분 이내',
      tools: '프라이팬, 냄비',
      pref: '간단하고 든든한 밥반찬'
    },
    {
      ingredients: '신김치 반포기, 돼지고기, 두부 반모, 대파',
      servings: '2인분',
      time: '20분 이내',
      tools: '냄비',
      pref: '칼칼하고 깊은 국물 요리'
    },
    {
      ingredients: '참치캔 1개, 계란 2개, 양파 반개, 김치',
      servings: '1인분 (혼밥)',
      time: '10분 컷 초간단',
      tools: '프라이팬',
      pref: '초간단 자취 한그릇 요리'
    },
    {
      ingredients: '순두부 1봉, 계란 1개, 대파, 참치캔, 고춧가루',
      servings: '2인분',
      time: '20분 이내',
      tools: '냄비',
      pref: '얼큰하고 부드러운 국물 요리'
    },
    {
      ingredients: '식빵, 계란 2개, 치즈, 버터, 마늘',
      servings: '1인분 (혼밥)',
      time: '10분 컷 초간단',
      tools: '프라이팬, 전자레인지',
      pref: '고소하고 달콤한 브런치'
    },
    {
      ingredients: '돼지고기, 양파 1개, 대파, 버섯, 청양고추',
      servings: '2인분',
      time: '20분 이내',
      tools: '프라이팬',
      pref: '매콤달콤 불맛 제육볶음'
    }
  ];

  randomRecipeBtn.addEventListener('click', () => {
    // 랜덤 세트 선택
    const randomPick = randomCombos[Math.floor(Math.random() * randomCombos.length)];

    // 폼 값 자동 채우기
    ingredientsInput.value = randomPick.ingredients;
    document.getElementById('servings').value = randomPick.servings;
    document.getElementById('cookingTime').value = randomPick.time;
    document.getElementById('tools').value = randomPick.tools;
    document.getElementById('preference').value = randomPick.pref;

    // 칩 동기화 & 비우기 버튼 노출
    syncChipsWithInput();
    toggleClearButton();

    // 버튼 피드백 애니메이션
    randomRecipeBtn.style.transform = 'scale(0.95)';
    setTimeout(() => {
      randomRecipeBtn.style.transform = '';
    }, 150);
  });

  // 4. 레시피 생성 폼 제출 이벤트
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const ingredients = ingredientsInput.value.trim();
    const servings = document.getElementById('servings').value;
    const cookingTime = document.getElementById('cookingTime').value;
    const tools = document.getElementById('tools').value.trim();
    const allergies = document.getElementById('allergies').value.trim();
    const preference = document.getElementById('preference').value.trim();

    if (!ingredients) {
      showError('보유 재료를 1개 이상 입력하거나 아래 칩을 눌러주세요!');
      return;
    }

    // UI 상태: 로딩 시작
    hideError();
    recipeSelectionSection.classList.add('hidden');
    resultSection.classList.add('hidden');
    loadingSection.classList.remove('hidden');
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 3가지 요리 & 유튜브 영상 분석 중...';

    try {
      const response = await fetch('/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ingredients,
          servings,
          cooking_time: cookingTime,
          tools,
          allergies,
          preference,
        }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        throw new Error(result.error || '레시피 생성 중 오류가 발생했습니다.');
      }

      currentRecipeList = result.recipes || [];
      if (currentRecipeList.length === 0) {
        throw new Error('생성된 레시피가 없습니다.');
      }

      // 3종 레시피 선택 탭 렌더링
      renderRecipeSelectionTabs(currentRecipeList);

      // 첫 번째 레시피를 기본 선택하여 상세 표시
      selectRecipeByIndex(0);

      // 결과 영역으로 스크롤 이동
      recipeSelectionSection.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
      console.error('API Error:', error);
      showError(error.message);
    } finally {
      loadingSection.classList.add('hidden');
      generateBtn.disabled = false;
      generateBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 3가지 맞춤 요리 & 영상 추천받기';
    }
  });

  // 5. 3가지 요리 후보 선택 탭 렌더링 함수
  function renderRecipeSelectionTabs(recipes) {
    recipeTabs.innerHTML = '';
    recipes.forEach((recipe, index) => {
      const tabCard = document.createElement('div');
      tabCard.className = `recipe-tab-card ${index === 0 ? 'active-tab' : ''}`;
      tabCard.setAttribute('data-index', index);
      tabCard.innerHTML = `
        <span class="tab-tag">${recipe.category_tag || `추천 ${index + 1}`}</span>
        <h4 class="tab-title">${recipe.menu_name}</h4>
        <div class="tab-meta">
          <span>⏱ ${recipe.estimated_time || '20분'}</span>
          <span>⚡ ${recipe.nutrition_info?.calories || '약 400 kcal'}</span>
        </div>
      `;

      tabCard.addEventListener('click', () => {
        selectRecipeByIndex(index);
      });

      recipeTabs.appendChild(tabCard);
    });

    recipeSelectionSection.classList.remove('hidden');
  }

  // 6. 특정 인덱스의 레시피 선택 및 상세 뷰 표시
  function selectRecipeByIndex(index) {
    activeRecipeIndex = index;
    currentRecipeData = currentRecipeList[index];

    const tabCards = recipeTabs.querySelectorAll('.recipe-tab-card');
    tabCards.forEach((card, i) => {
      if (i === index) {
        card.classList.add('active-tab');
      } else {
        card.classList.remove('active-tab');
      }
    });

    renderRecipeDetail(currentRecipeData);
  }

  // 7. 레시피 상세 화면 바인딩 함수
  function renderRecipeDetail(recipe) {
    document.getElementById('categoryBadge').textContent = recipe.category_tag || '✨ AI 맞춤 추천 요리';
    document.getElementById('menuName').textContent = recipe.menu_name || '추천 요리';
    document.getElementById('oneLineIntro').textContent = recipe.one_line_intro || '';
    document.getElementById('metaTime').textContent = recipe.estimated_time || '20분';
    document.getElementById('metaServings').textContent = recipe.servings || '2인분';
    document.getElementById('metaDifficulty').textContent = recipe.difficulty || '초급';

    // 유튜브 정보 바인딩
    const yt = recipe.youtube || {};
    document.getElementById('ytTitle').textContent = yt.title || `${recipe.menu_name} 영상 레시피`;
    document.getElementById('ytChannel').textContent = yt.channel ? `${yt.channel}에서 시청 가능` : '유튜브에서 실제 조리 영상을 바로 확인해 보세요.';
    const ytLink = document.getElementById('ytLink');
    ytLink.href = yt.youtube_url || `https://www.youtube.com/results?search_query=${encodeURIComponent(recipe.menu_name + ' 만드는법')}`;

    // 스마트 영양 성분 렌더링
    const nutri = recipe.nutrition_info || {};
    document.getElementById('nutriCalories').textContent = nutri.calories || '약 400 kcal';
    document.getElementById('nutriCarbs').textContent = nutri.carbs || '-';
    document.getElementById('nutriProtein').textContent = nutri.protein || '-';
    document.getElementById('nutriFat').textContent = nutri.fat || '-';
    document.getElementById('nutriSodium').textContent = nutri.sodium || '-';
    document.getElementById('nutriSummary').innerHTML = `<i class="fa-solid fa-lightbulb"></i> ${nutri.health_summary || '균형 잡힌 영양 식단입니다.'}`;

    // 식재료 목록 채우기
    const ingredientsList = document.getElementById('ingredientsList');
    ingredientsList.innerHTML = '';
    (recipe.ingredients_list || []).forEach(item => {
      const li = document.createElement('li');
      li.textContent = item;
      ingredientsList.appendChild(li);
    });

    // 양념장 비율 채우기
    const sauceList = document.getElementById('sauceList');
    sauceList.innerHTML = '';
    (recipe.sauce_ratios || []).forEach(item => {
      const li = document.createElement('li');
      li.textContent = item;
      sauceList.appendChild(li);
    });

    // 조리 순서 채우기
    const cookingSteps = document.getElementById('cookingSteps');
    cookingSteps.innerHTML = '';
    (recipe.cooking_steps || []).forEach(step => {
      const li = document.createElement('li');
      li.textContent = step;
      cookingSteps.appendChild(li);
    });

    // 실패 방지 팁 채우기
    const failProofTips = document.getElementById('failProofTips');
    failProofTips.innerHTML = '';
    (recipe.fail_proof_tips || []).forEach(tip => {
      const li = document.createElement('li');
      li.textContent = tip;
      failProofTips.appendChild(li);
    });

    // 대체 식재료 가이드 채우기
    const substituteGuide = document.getElementById('substituteGuide');
    substituteGuide.innerHTML = '';
    (recipe.substitute_guide || []).forEach(guide => {
      const li = document.createElement('li');
      li.textContent = guide;
      substituteGuide.appendChild(li);
    });

    updateBookmarkButtonState();
    resultSection.classList.remove('hidden');
  }

  // 8. 즐겨찾기 (LocalStorage) 로직
  function getSavedBookmarks() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function saveBookmarks(bookmarks) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarks));
    updateBookmarkBadge();
  }

  function updateBookmarkBadge() {
    const list = getSavedBookmarks();
    bookmarkCountBadge.textContent = list.length;
  }

  function isCurrentRecipeBookmarked() {
    if (!currentRecipeData) return false;
    const list = getSavedBookmarks();
    return list.some(item => item.menu_name === currentRecipeData.menu_name);
  }

  function updateBookmarkButtonState() {
    if (isCurrentRecipeBookmarked()) {
      bookmarkBtn.innerHTML = '<i class="fa-solid fa-star"></i> <span>보관됨</span>';
      bookmarkBtn.classList.add('btn-bookmarked');
    } else {
      bookmarkBtn.innerHTML = '<i class="fa-regular fa-star"></i> <span>즐겨찾기 저장</span>';
      bookmarkBtn.classList.remove('btn-bookmarked');
    }
  }

  bookmarkBtn.addEventListener('click', () => {
    if (!currentRecipeData) return;
    let list = getSavedBookmarks();
    const existingIndex = list.findIndex(i => i.menu_name === currentRecipeData.menu_name);

    if (existingIndex >= 0) {
      list.splice(existingIndex, 1);
    } else {
      const toSave = {
        ...currentRecipeData,
        savedAt: new Date().toLocaleDateString('ko-KR')
      };
      list.unshift(toSave);
    }

    saveBookmarks(list);
    updateBookmarkButtonState();
  });

  // 보관함 모달 열기 & 닫기
  openBookmarksBtn.addEventListener('click', () => {
    renderBookmarkList();
    bookmarkDrawer.classList.remove('hidden');
  });

  closeDrawerBtn.addEventListener('click', () => {
    bookmarkDrawer.classList.add('hidden');
  });

  bookmarkDrawer.addEventListener('click', (e) => {
    if (e.target === bookmarkDrawer) {
      bookmarkDrawer.classList.add('hidden');
    }
  });

  function renderBookmarkList() {
    const list = getSavedBookmarks();
    bookmarkList.innerHTML = '';

    if (list.length === 0) {
      bookmarkList.innerHTML = '<div class="empty-bookmarks"><i class="fa-regular fa-folder-open fa-2x"></i><p style="margin-top:10px;">보관된 레시피가 없습니다.<br>마음에 드는 요리를 별표로 저장해 보세요!</p></div>';
      return;
    }

    list.forEach((item, index) => {
      const card = document.createElement('div');
      card.className = 'bookmark-item';
      card.innerHTML = `
        <div class="bookmark-item-title">${item.menu_name}</div>
        <div class="bookmark-item-meta">⏱ ${item.estimated_time || '20분'} | 👥 ${item.servings || '2인분'} | ⚡ ${item.nutrition_info?.calories || '약 400 kcal'}</div>
        <div class="bookmark-item-actions">
          <button class="btn btn-primary btn-sm load-btn" data-index="${index}">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> 보기
          </button>
          <button class="btn btn-secondary btn-sm delete-btn" data-index="${index}">
            <i class="fa-solid fa-trash-can"></i> 삭제
          </button>
        </div>
      `;
      bookmarkList.appendChild(card);
    });

    bookmarkList.querySelectorAll('.load-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = e.currentTarget.getAttribute('data-index');
        const selected = list[idx];
        if (selected) {
          currentRecipeData = selected;
          renderRecipeDetail(selected);
          bookmarkDrawer.classList.add('hidden');
          resultSection.scrollIntoView({ behavior: 'smooth' });
        }
      });
    });

    bookmarkList.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = e.currentTarget.getAttribute('data-index');
        list.splice(idx, 1);
        saveBookmarks(list);
        renderBookmarkList();
        updateBookmarkButtonState();
      });
    });
  }

  // 9. 인쇄하기 (Print) 기능
  printBtn.addEventListener('click', () => {
    if (!currentRecipeData) return;
    window.print();
  });

  // 10. 클립보드 복사 기능
  copyBtn.addEventListener('click', async () => {
    if (!currentRecipeData) return;

    const formattedText = generateRecipeText(currentRecipeData);
    try {
      await navigator.clipboard.writeText(formattedText);
      const originalHtml = copyBtn.innerHTML;
      copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> 복사 완료!';
      copyBtn.style.background = '#c6f6d5';
      setTimeout(() => {
        copyBtn.innerHTML = originalHtml;
        copyBtn.style.background = '';
      }, 2000);
    } catch (err) {
      alert('클립보드 복사에 실패했습니다. 수동으로 복사해 주세요.');
    }
  });

  // 11. 레시피 텍스트(.txt) 파일 다운로드 기능
  downloadBtn.addEventListener('click', () => {
    if (!currentRecipeData) return;

    const formattedText = generateRecipeText(currentRecipeData);
    const blob = new Blob([formattedText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentRecipeData.menu_name || 'AI_레시피'}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  // 12. 텍스트 포맷팅 헬퍼 함수
  function generateRecipeText(r) {
    const nutri = r.nutrition_info || {};
    const ytUrl = r.youtube?.youtube_url || '';
    return `[ AI Recipe Studio - 맞춤형 스마트 레시피 ]\n\n` +
      `🍳 요리명: ${r.menu_name} (${r.category_tag || '추천 요리'})\n` +
      `💡 한줄 소개: ${r.one_line_intro}\n` +
      `⏱ 소요시간: ${r.estimated_time} | 👥 인원: ${r.servings} | 📊 난이도: ${r.difficulty || '초급'}\n` +
      `🥗 칼로리 & 영양: ${nutri.calories || '약 400 kcal'} (탄수화물: ${nutri.carbs || '-'}, 단백질: ${nutri.protein || '-'}, 지방: ${nutri.fat || '-'}, 나트륨: ${nutri.sodium || '-'})\n` +
      `📺 유튜브 영상 링크: ${ytUrl}\n\n` +
      `[ 🥗 필요 식재료 ]\n` +
      (r.ingredients_list || []).map(i => `• ${i}`).join('\n') + `\n\n` +
      `[ 🥄 황금 양념 비율 ]\n` +
      (r.sauce_ratios || []).map(s => `• ${s}`).join('\n') + `\n\n` +
      `[ 👨‍🍳 조리 순서 ]\n` +
      (r.cooking_steps || []).map((step, idx) => `${idx + 1}. ${step}`).join('\n') + `\n\n` +
      `[ 🛡 실패 방지 핵심 팁 ]\n` +
      (r.fail_proof_tips || []).map(t => `- ${t}`).join('\n') + `\n\n` +
      `[ 🔄 재료 대체 가이드 ]\n` +
      (r.substitute_guide || []).map(g => `- ${g}`).join('\n');
  }

  // 에러 메시지 표시 헬퍼
  function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.classList.remove('hidden');
    errorAlert.scrollIntoView({ behavior: 'smooth' });
  }

  function hideError() {
    errorAlert.classList.add('hidden');
  }

  // --- PWA (Progressive Web App) 서비스 워커 등록 및 설치 지원 ---
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then((reg) => {
          console.log('Service Worker 등록 성공:', reg.scope);
        })
        .catch((err) => {
          console.log('Service Worker 등록 실패:', err);
        });
    });
  }

  // PWA 설치 버튼 핸들러
  let deferredPrompt = null;
  const installPwaBtn = document.getElementById('installPwaBtn');

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (installPwaBtn) {
      installPwaBtn.classList.remove('hidden');
    }
  });

  if (installPwaBtn) {
    installPwaBtn.addEventListener('click', async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      console.log('PWA 설치 응답:', outcome);
      deferredPrompt = null;
      installPwaBtn.classList.add('hidden');
    });
  }

  window.addEventListener('appinstalled', () => {
    console.log('PWA가 성공적으로 설치되었습니다!');
    if (installPwaBtn) {
      installPwaBtn.classList.add('hidden');
    }
  });
});