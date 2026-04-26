/* ============================================================
   Basira — main.js
   Vanilla JS, no dependencies. Three concerns:
     1. Project-chapter scroll-in fade/scale
     2. Timelapse autoplay on view + click toggle
     3. Before/after sliders (drag desktop, tap mobile, auto-sweep)
   ============================================================ */

(() => {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const coarsePointer = window.matchMedia("(pointer: coarse)").matches;

  /* ----------------------------------------------------------
     1. Project-chapter scroll-in (.chapter-project → .is-visible)
     ---------------------------------------------------------- */
  const projectChapters = document.querySelectorAll(".chapter-project");
  if (reduceMotion) {
    projectChapters.forEach((el) => el.classList.add("is-visible"));
  } else if ("IntersectionObserver" in window) {
    // Use rootMargin not threshold — chapters are taller than the viewport,
    // so a fraction-of-target threshold can be unreachable. Fire as soon as
    // the chapter has crossed ~15% into the viewport from the bottom edge.
    const io = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-visible");
            obs.unobserve(e.target); // once per page load
          }
        });
      },
      { threshold: 0, rootMargin: "0px 0px -15% 0px" }
    );
    projectChapters.forEach((el) => io.observe(el));
  } else {
    projectChapters.forEach((el) => el.classList.add("is-visible"));
  }

  /* ----------------------------------------------------------
     2. Timelapse autoplay on scroll-into-view + click-to-toggle
     ---------------------------------------------------------- */
  const aoiVideos = document.querySelectorAll(".aoi-video");
  if (!reduceMotion && "IntersectionObserver" in window) {
    const vio = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          const v = e.target;
          if (e.isIntersecting) {
            const p = v.play();
            if (p && typeof p.catch === "function") p.catch(() => {});
          } else {
            v.pause();
          }
        });
      },
      { threshold: 0.5 }
    );
    aoiVideos.forEach((v) => vio.observe(v));
  }

  aoiVideos.forEach((v) => {
    v.addEventListener("click", () => {
      if (v.paused) {
        const p = v.play();
        if (p && typeof p.catch === "function") p.catch(() => {});
      } else {
        v.pause();
      }
    });
  });

  /* ----------------------------------------------------------
     3. Before/after sliders
     ---------------------------------------------------------- */
  const sliders = document.querySelectorAll(".ba-slider");
  sliders.forEach(initSlider);

  function initSlider(el) {
    const before = el.dataset.before;
    const after = el.dataset.after;
    const aspect = el.dataset.aspect || "1.857";
    const mask = el.dataset.mask;
    const backdrop = el.dataset.backdrop;
    const labelBefore = el.dataset.labelBefore || "Before";
    const labelAfter = el.dataset.labelAfter || "After";

    el.style.setProperty("--ba-aspect", aspect);
    el.style.setProperty("--ba-pos", "50%");

    const maskStyle = mask
      ? `style="-webkit-mask-image: url('${mask}'); mask-image: url('${mask}');"`
      : "";
    el.innerHTML = `
      ${backdrop ? `<img class="ba-backdrop" src="${backdrop}" alt="" aria-hidden="true">` : ""}
      <img class="ba-img ba-before" src="${before}" alt="" ${maskStyle}>
      <img class="ba-img ba-after"  src="${after}"  alt="" ${maskStyle}>
      <div class="ba-handle" role="slider" tabindex="0"
           aria-label="Before-after divider"
           aria-valuemin="0" aria-valuemax="100" aria-valuenow="50"></div>
      <span class="ba-label ba-label-before">${labelBefore}</span>
      <span class="ba-label ba-label-after">${labelAfter}</span>
    `;

    const handle = el.querySelector(".ba-handle");
    let armed = false;

    const setPos = (pct) => {
      pct = Math.max(0, Math.min(100, pct));
      el.style.setProperty("--ba-pos", pct + "%");
      handle.setAttribute("aria-valuenow", String(Math.round(pct)));
    };

    /* Pointer drag (desktop fine pointer) */
    const pointerToPct = (clientX) => {
      const r = el.getBoundingClientRect();
      return ((clientX - r.left) / r.width) * 100;
    };

    if (!coarsePointer) {
      let dragging = false;
      const onDown = (ev) => {
        dragging = true;
        armed = true;
        el.dataset.armed = "1";
        handle.setPointerCapture && handle.setPointerCapture(ev.pointerId);
        setPos(pointerToPct(ev.clientX));
        ev.preventDefault();
      };
      const onMove = (ev) => {
        if (!dragging) return;
        setPos(pointerToPct(ev.clientX));
      };
      const onUp = () => { dragging = false; };

      handle.addEventListener("pointerdown", onDown);
      el.addEventListener("pointerdown", (ev) => {
        if (ev.target === handle) return;
        // Click anywhere in the slider also moves the handle.
        armed = true;
        el.dataset.armed = "1";
        setPos(pointerToPct(ev.clientX));
      });
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
    } else {
      /* Coarse pointer (touch): tap-to-toggle 0% / 100% */
      el.addEventListener("click", () => {
        armed = true;
        el.dataset.armed = "1";
        const cur = parseFloat(getComputedStyle(el).getPropertyValue("--ba-pos")) || 50;
        setPos(cur < 50 ? 100 : 0);
      });
    }

    /* Keyboard a11y */
    handle.addEventListener("keydown", (ev) => {
      const cur = parseFloat(handle.getAttribute("aria-valuenow")) || 50;
      let next = cur;
      if (ev.key === "ArrowLeft") next = cur - 2;
      else if (ev.key === "ArrowRight") next = cur + 2;
      else if (ev.key === "Home") next = 0;
      else if (ev.key === "End") next = 100;
      else return;
      armed = true;
      el.dataset.armed = "1";
      setPos(next);
      ev.preventDefault();
    });

    /* Auto-sweep on first scroll-into-view */
    if (reduceMotion || !("IntersectionObserver" in window)) {
      setPos(50);
      return;
    }

    const sweep = () => {
      const start = performance.now();
      const dur = 1500;
      // 50 → 85 → 50, ease-out applied to the unit position
      const tick = (now) => {
        if (armed) return; // user took over mid-sweep
        const t = Math.min(1, (now - start) / dur);
        const eased = 1 - Math.pow(1 - t, 3); // cubic ease-out
        // triangle: 0..0.5 ramps up, 0.5..1 ramps down
        const tri = eased < 0.5 ? eased * 2 : (1 - eased) * 2;
        const pct = 50 + tri * 35;
        setPos(pct);
        if (t < 1) requestAnimationFrame(tick);
        else setPos(50);
      };
      requestAnimationFrame(tick);
    };

    const sio = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            obs.unobserve(e.target);
            sweep();
          }
        });
      },
      { threshold: 0.5 }
    );
    sio.observe(el);
  }
})();
