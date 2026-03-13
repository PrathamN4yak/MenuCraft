/* ============================================
   MenuCraft — Main JavaScript
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {

  /* ── Navbar scroll effect ── */
  const navbar = document.getElementById('navbar');
  const alwaysScrolled = navbar?.dataset.alwaysScrolled === 'true';

  function checkScroll() {
    if (alwaysScrolled) {
      navbar.classList.add('scrolled');
      return;
    }
    if (window.scrollY > 60) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  }

  // Run immediately
  checkScroll();
  // Run again after full page load (browser scrolls to #anchor AFTER DOMContentLoaded)
  window.addEventListener('load', () => {
    checkScroll();
    // Extra safety: browser may scroll to anchor just after load event too
    setTimeout(checkScroll, 50);
    setTimeout(checkScroll, 200);
  });
  window.addEventListener('scroll', checkScroll);

  /* ── Mobile hamburger menu ── */
  const hamburger = document.getElementById('hamburger');
  const mobileMenu = document.getElementById('mobile-menu');
  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', () => {
      mobileMenu.classList.toggle('open');
      hamburger.classList.toggle('active');
    });
  }

  /* ── Scroll reveal animation ── */
  const revealElements = document.querySelectorAll('.reveal');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, { threshold: 0.12 });

  revealElements.forEach(el => observer.observe(el));

  /* ── Animated counter for hero stats ── */
  function animateCounter(el, target, duration = 1800) {
    let start = 0;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        el.textContent = target + (el.dataset.suffix || '');
        clearInterval(timer);
      } else {
        el.textContent = Math.floor(start) + (el.dataset.suffix || '');
      }
    }, 16);
  }

  const counters = document.querySelectorAll('[data-counter]');
  const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !entry.target.dataset.animated) {
        entry.target.dataset.animated = 'true';
        animateCounter(entry.target, parseInt(entry.target.dataset.counter));
      }
    });
  }, { threshold: 0.5 });

  counters.forEach(el => counterObserver.observe(el));

  /* ── Active nav link highlight ── */
  const sections = document.querySelectorAll('section[id]');
  const navLinks = document.querySelectorAll('.navbar-links a');
  window.addEventListener('scroll', () => {
    let current = '';
    sections.forEach(section => {
      if (window.scrollY >= section.offsetTop - 100) {
        current = section.getAttribute('id');
      }
    });
    navLinks.forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('href') === `#${current}`) {
        link.classList.add('active');
      }
    });
  });

});