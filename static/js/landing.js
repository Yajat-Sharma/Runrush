/* ═══════════════════════════════════════
   RunRush Landing v3 – Parallax + Tilt
   Pure JS – no libraries needed
   ═══════════════════════════════════════ */

(function () {
    'use strict';

    const IS_MOBILE = window.innerWidth <= 700;

    /* ── DOM References ── */
    const hero = document.getElementById('hero');
    const cityBg = document.getElementById('cityBg');
    const runner = document.getElementById('runner');
    const speedLines = document.getElementById('speedLines');
    const heroContent = document.getElementById('heroContent');
    const icons = document.querySelectorAll('.floating-icon');
    const cards = document.querySelectorAll('.card-3d');

    if (!hero) return;

    /* ═══════════ MOUSE TILT + PARALLAX ═══════════ */
    if (!IS_MOBILE) {
        hero.addEventListener('mousemove', function (e) {
            var rect = hero.getBoundingClientRect();
            var x = e.clientX - rect.left;
            var y = e.clientY - rect.top;
            var cx = rect.width / 2;
            var cy = rect.height / 2;

            // Rotation values (max ±3deg X, ±2deg Y)
            var rotY = ((x - cx) / cx) * 3;
            var rotX = ((cy - y) / cy) * 2;

            // Hero container tilt
            hero.style.transform =
                'perspective(800px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg) scale(1.01)';

            // City layer – moves opposite (far)
            if (cityBg) {
                cityBg.style.transform =
                    'translateX(' + (rotY * 2) + 'px) translateY(' + (rotX * 1.5) + 'px) translateZ(-30px) scale(1.15)';
            }

            // Runner layer – more responsive (front)
            if (runner) {
                runner.style.transform =
                    'translateZ(20px) translateX(' + (rotY * 1.5) + 'px) translateY(' + (rotX - 3) + 'px) scale(1.05)';
            }

            // Speed lines shift
            if (speedLines) {
                speedLines.style.transform =
                    'rotate(5deg) translateX(' + (rotY * 2) + 'px) translateY(' + (rotX) + 'px) translateZ(-10px)';
            }

            // Content slight movement
            if (heroContent) {
                heroContent.style.transform =
                    'translateZ(30px) translateX(' + (rotY * 1.2) + 'px) translateY(' + (rotX * 0.8) + 'px)';
            }

            // Icons drift
            icons.forEach(function (icon, i) {
                var factor = (i + 1) * 0.6;
                icon.style.transform =
                    'translateX(' + (rotY * factor) + 'px) translateY(' + (rotX * factor) + 'px)';
            });
        });

        // Reset on leave
        hero.addEventListener('mouseleave', function () {
            hero.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg) scale(1)';
            if (cityBg) cityBg.style.transform = 'translateZ(-30px) scale(1.15)';
            if (runner) runner.style.transform = 'translateZ(20px) scale(1.05)';
            if (speedLines) speedLines.style.transform = 'rotate(5deg) translateZ(-10px)';
            if (heroContent) heroContent.style.transform = 'translateZ(30px)';
            icons.forEach(function (icon) { icon.style.transform = ''; });
        });
    }

    /* ═══════════ SCROLL PARALLAX ═══════════ */
    window.addEventListener('scroll', function () {
        var scrollY = window.scrollY;
        var maxScroll = window.innerHeight;

        if (scrollY <= maxScroll) {
            var progress = scrollY / maxScroll; // 0 → 1

            if (cityBg && !IS_MOBILE) {
                cityBg.style.transform =
                    'translateY(' + (progress * 35) + 'px) translateZ(-30px) scale(1.15)';
            }
            if (runner && !IS_MOBILE) {
                runner.style.transform =
                    'translateZ(20px) translateY(' + (progress * -18) + 'px) scale(1.05)';
            }
            if (speedLines) {
                speedLines.style.opacity = String(1 - progress * 0.6);
            }
        }
    });

    /* ═══════════ CARD INTERSECTION OBSERVER ═══════════ */
    if (cards.length) {
        var cardObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.style.transform = 'rotateY(4deg) rotateX(2deg) translateZ(15px)';
                    entry.target.style.opacity = '1';
                }
            });
        }, { threshold: 0.25 });

        cards.forEach(function (c) {
            if (!IS_MOBILE) {
                c.style.opacity = '0';
                c.style.transform = 'rotateY(0) rotateX(0) translateZ(0)';
                c.style.transition = 'transform 0.5s cubic-bezier(0.23,1,0.32,1), opacity 0.5s ease, box-shadow 0.35s';
            }
            cardObserver.observe(c);
        });
    }

    /* ═══════════ HERO CONTENT ENTRANCE ═══════════ */
    window.addEventListener('load', function () {
        var elements = ['.hero-tag', 'h1', 'p', '.hero-btns'];
        var delay = 200;

        elements.forEach(function (sel, i) {
            var el = hero.querySelector(sel);
            if (el) {
                setTimeout(function () {
                    el.style.transition = 'opacity 0.55s ease, transform 0.55s ease';
                    el.style.opacity = '1';
                    el.style.transform = 'translateY(0)';
                }, delay + i * 180);
            }
        });
    });

})();
