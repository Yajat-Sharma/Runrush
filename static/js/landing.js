/* ==========================================================================
   RunRush Landing Page – 3-Slide Mobile-First Intro Controller
   CSS Scroll-Snap, Subtle Parallax, Image Pre-decoding, Zero Layout Shift
   ========================================================================== */

(function () {
  'use strict';

  var STORAGE_KEY = 'runrush_intro_finished';
  var totalSlides = 3;
  var currentSlide = 0;

  var viewport = document.getElementById('slidesViewport');
  var slides = document.querySelectorAll('.slide');
  var slidePhotos = document.querySelectorAll('.slide-photo');
  var skipBtn = document.getElementById('skipBtn');
  var primaryCtaBtn = document.getElementById('primaryCtaBtn');
  var ctaLabelContinue = document.getElementById('ctaLabelContinue');
  var ctaLabelStart = document.getElementById('ctaLabelStart');
  var secondaryActionRow = document.getElementById('secondaryActionRow');
  var signInLink = document.getElementById('signInLink');
  var dotButtons = document.querySelectorAll('.dot-btn');

  var isReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function setIntroFinished() {
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch (e) {
      /* Quota exceeded or private browsing mode blocking storage */
    }
  }

  /* ── 1. Image Preloading & Decoding (No Pop-in) ── */
  function preloadSlideImages() {
    var images = [
      { id: 'slidePhoto2', src: '/static/img/landing-2.webp?v=6' },
      { id: 'slidePhoto3', src: '/static/img/landing-3.webp?v=6' }
    ];

    images.forEach(function (item) {
      var img = new Image();
      img.src = item.src;

      function onReady() {
        var el = document.getElementById(item.id);
        if (el) {
          el.classList.add('is-ready');
        }
      }

      if ('decode' in img) {
        img.decode().then(onReady).catch(onReady);
      } else {
        img.onload = onReady;
        img.onerror = onReady;
      }
    });
  }

  // Defer image decode until after the first slide paints
  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(preloadSlideImages);
  } else {
    setTimeout(preloadSlideImages, 120);
  }

  /* ── 2. Update UI on Active Slide Change ── */
  function setActiveSlide(index) {
    if (index === currentSlide && slides[index] && slides[index].classList.contains('is-active')) {
      return;
    }
    currentSlide = index;

    // Toggle active classes on slides (triggers fade + 12px upward translate)
    slides.forEach(function (slide, i) {
      if (i === currentSlide) {
        slide.classList.add('is-active');
      } else {
        slide.classList.remove('is-active');
      }
    });

    // Update pagination dots
    dotButtons.forEach(function (dot) {
      var dotIndex = parseInt(dot.getAttribute('data-slide'), 10);
      if (dotIndex === currentSlide) {
        dot.classList.add('active');
        dot.setAttribute('aria-current', 'step');
      } else {
        dot.classList.remove('active');
        dot.removeAttribute('aria-current');
      }
    });

    // Update CTA Button & Secondary Row
    if (currentSlide === totalSlides - 1) {
      // Slide 3: Cross-fade to "Get started"
      if (ctaLabelContinue) ctaLabelContinue.classList.remove('is-active');
      if (ctaLabelStart) ctaLabelStart.classList.add('is-active');
      if (primaryCtaBtn) primaryCtaBtn.setAttribute('aria-label', 'Get started with RunRush');
      if (secondaryActionRow) secondaryActionRow.classList.add('is-visible');
    } else {
      // Slides 1 & 2: Cross-fade to "Continue"
      if (ctaLabelStart) ctaLabelStart.classList.remove('is-active');
      if (ctaLabelContinue) ctaLabelContinue.classList.add('is-active');
      if (primaryCtaBtn) primaryCtaBtn.setAttribute('aria-label', 'Continue to next slide');
      if (secondaryActionRow) secondaryActionRow.classList.remove('is-visible');
    }
  }

  /* ── 3. Scroll-To Helper ── */
  function scrollToSlide(index) {
    if (index < 0) index = 0;
    if (index >= totalSlides) index = totalSlides - 1;

    if (viewport) {
      var targetLeft = index * viewport.clientWidth;
      viewport.scrollTo({
        left: targetLeft,
        behavior: isReducedMotion ? 'auto' : 'smooth'
      });
    }
    setActiveSlide(index);
  }

  /* ── 4. IntersectionObserver for Slide Detection ── */
  if ('IntersectionObserver' in window && viewport) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          var idx = parseInt(entry.target.getAttribute('data-index'), 10);
          if (!isNaN(idx)) {
            setActiveSlide(idx);
          }
        }
      });
    }, {
      root: viewport,
      threshold: 0.6
    });

    slides.forEach(function (slide) {
      observer.observe(slide);
    });
  }

  /* ── 5. Parallax on Scroll (18% Slower Movement) ── */
  var ticking = false;
  function handleScroll() {
    if (!viewport) return;
    var scrollLeft = viewport.scrollLeft;
    var width = viewport.clientWidth;
    if (!width) return;

    // Fallback active slide detection for browsers with delayed observer
    var computedIndex = Math.round(scrollLeft / width);
    if (computedIndex >= 0 && computedIndex < totalSlides) {
      setActiveSlide(computedIndex);
    }

    // Subtle parallax effect on photo layers
    if (!isReducedMotion) {
      slidePhotos.forEach(function (photo, i) {
        var slideOffset = (i * width) - scrollLeft;
        var parallaxX = slideOffset * 0.18;
        photo.style.transform = 'translate3d(' + parallaxX.toFixed(1) + 'px, 0, 0)';
      });
    }

    ticking = false;
  }

  if (viewport) {
    viewport.addEventListener('scroll', function () {
      if (!ticking) {
        window.requestAnimationFrame(handleScroll);
        ticking = true;
      }
    }, { passive: true });
  }

  /* ── 6. Controls Interaction ── */
  // Primary CTA Button
  if (primaryCtaBtn) {
    primaryCtaBtn.addEventListener('click', function (e) {
      e.preventDefault();
      if (currentSlide < totalSlides - 1) {
        scrollToSlide(currentSlide + 1);
      } else {
        setIntroFinished();
        window.location.href = '/register';
      }
    });
  }

  // Pagination Dot Buttons
  dotButtons.forEach(function (dot) {
    dot.addEventListener('click', function () {
      var target = parseInt(dot.getAttribute('data-slide'), 10);
      if (!isNaN(target)) {
        scrollToSlide(target);
      }
    });
  });

  // Skip Button
  if (skipBtn) {
    skipBtn.addEventListener('click', function (e) {
      e.preventDefault();
      setIntroFinished();
      window.location.href = '/login';
    });
  }

  // Secondary Sign-in Link
  if (signInLink) {
    signInLink.addEventListener('click', function () {
      setIntroFinished();
    });
  }

  // Keyboard Arrow Navigation
  window.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') {
      if (currentSlide < totalSlides - 1) {
        scrollToSlide(currentSlide + 1);
      }
    } else if (e.key === 'ArrowLeft') {
      if (currentSlide > 0) {
        scrollToSlide(currentSlide - 1);
      }
    }
  });

  /* ── 7. Resize & Orientation Change (Zero Jump) ── */
  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      if (viewport) {
        // Re-align track to current slide without animation
        var originalBehavior = viewport.style.scrollBehavior;
        viewport.style.scrollBehavior = 'auto';
        viewport.scrollLeft = currentSlide * viewport.clientWidth;
        setTimeout(function () {
          viewport.style.scrollBehavior = originalBehavior || '';
        }, 50);
      }
    }, 80);
  });

})();
