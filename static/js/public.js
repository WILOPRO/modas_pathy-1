// Inicialización de AOS, GSAP, ScrollTrigger y VanillaTilt
document.addEventListener('DOMContentLoaded', () => {
  // 1) AOS
  AOS.init({ duration: 700, once: true });

  // 2) GSAP + ScrollTrigger
  gsap.registerPlugin(ScrollTrigger);

  // 2.1) Animación del hero (texto y botón)
  gsap.from('.lead', {
    duration: 1.2,
    y: -30,
    opacity: 0,
    ease: 'power3.out'
  });
  gsap.from('.btn-primary', {
    duration: 1,
    scale: 0.5,
    opacity: 0,
    delay: 0.3,
    ease: 'back.out(1.7)'
  });

  // 2.2) Animación de las cards al hacer scroll
  gsap.utils.toArray('.card').forEach((card, i) => {
    gsap.from(card, {
      scrollTrigger: {
        trigger: card,
        start: 'top 80%',
      },
      y: 50,
      opacity: 0,
      duration: 0.6,
      delay: i * 0.1,
      ease: 'power2.out'
    });
  });

  // 3) Efecto tilt sobre las cards
  VanillaTilt.init(document.querySelectorAll('.card'), {
    max: 15,
    speed: 300,
    glare: true,
    'max-glare': 0.2
  });

  // 4) Bounce sutil al pasar por el botón de WhatsApp
  document.querySelectorAll('.btn-feedback').forEach(btn => {
    btn.addEventListener('mouseenter', () => {
      gsap.to(btn, { scale: 1.05, duration: 0.3, ease: 'power1.out' });
    });
    btn.addEventListener('mouseleave', () => {
      gsap.to(btn, { scale: 1, duration: 0.3, ease: 'power1.out' });
    });
  });
  

// Actualiza el mensaje de WhatsApp con el color seleccionado
  const colorSelect = document.getElementById('colorSelect');
  const waText = document.getElementById('wa_text');
  if (colorSelect && waText) {
    const baseText = waText.value;
    const updateText = () => {
      const color = colorSelect.value;
      waText.value = baseText.replace('COLOR_PLACEHOLDER', 'color ' + color);
    };
    colorSelect.addEventListener('change', updateText);
    updateText();
  }
});
// ═══════════════════════════════════════════════════════════════════════
//       MEJORAS JAVASCRIPT PARA INTERACCIÓN MODERNA
// ═══════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  
  // ─── Smooth scroll para enlaces internos ───
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ─── Lazy loading mejorado para imágenes ───
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src || img.src;
          img.classList.remove('loading');
          img.classList.add('loaded');
          observer.unobserve(img);
        }
      });
    });

    document.querySelectorAll('.img-wrapper img[loading="lazy"]').forEach(img => {
      imageObserver.observe(img);
    });
  }

  // ─── Animación del header al hacer scroll ───
  let lastScroll = 0;
  const header = document.querySelector('header.navbar');
  
  window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll > 100) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
    
    lastScroll = currentScroll;
  });

  // ─── Toast notifications para acciones ───
  function showToast(message, type = 'success') {
    const toastHTML = `
      <div class="toast align-items-center text-bg-${type} border-0 show" role="alert" style="position: fixed; top: 80px; right: 20px; z-index: 9999;">
        <div class="d-flex">
          <div class="toast-body">${message}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', toastHTML);
    
    setTimeout(() => {
      const toast = document.querySelector('.toast:last-child');
      if (toast) toast.remove();
    }, 3000);
  }

  // ─── Mejora de botones de WhatsApp con feedback ───
  document.querySelectorAll('a[href*="wa.me"]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const btnText = btn.innerHTML;
      btn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Abriendo WhatsApp...';
      btn.classList.add('disabled');
      
      setTimeout(() => {
        btn.innerHTML = btnText;
        btn.classList.remove('disabled');
      }, 2000);
    });
  });

  // ─── Contador animado para precios ───
  const animateValue = (element, start, end, duration) => {
    let startTimestamp = null;
    const step = (timestamp) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const value = progress * (end - start) + start;
      element.textContent = 'Bs ' + value.toFixed(2);
      if (progress < 1) {
        window.requestAnimationFrame(step);
      }
    };
    window.requestAnimationFrame(step);
  };

  // Animar precios al entrar en viewport
  if ('IntersectionObserver' in window) {
    const priceObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const priceElement = entry.target;
          const priceText = priceElement.textContent.replace('Bs ', '').trim();
          const priceValue = parseFloat(priceText);
          if (!isNaN(priceValue)) {
            animateValue(priceElement, 0, priceValue, 800);
            priceObserver.unobserve(priceElement);
          }
        }
      });
    });

    document.querySelectorAll('.fw-bold[class*="Bs"], .product-price').forEach(price => {
      priceObserver.observe(price);
    });
  }

  // ─── Filtro de búsqueda instantánea (opcional) ───
  const searchInput = document.querySelector('#searchInput');
  if (searchInput) {
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      const value = e.target.value.toLowerCase();
      
      if (value.length >= 2) {
        searchTimeout = setTimeout(() => {
          // Aquí podrías implementar búsqueda AJAX si lo deseas
          console.log('Buscando:', value);
        }, 500);
      }
    });
  }

  // ─── Mejora del sidebar en móvil ───
  const sidebar = document.getElementById('sidebarMenu');
  const sidebarToggle = document.getElementById('sidebarToggle');
  
  if (sidebar && sidebarToggle) {
    // Cerrar sidebar al hacer click fuera
    document.addEventListener('click', (e) => {
      if (sidebar.classList.contains('show') && 
          !sidebar.contains(e.target) && 
          !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove('show');
      }
    });

    // Prevenir scroll del body cuando sidebar está abierto
    const observer = new MutationObserver(() => {
      document.body.style.overflow = sidebar.classList.contains('show') ? 'hidden' : '';
    });
    observer.observe(sidebar, { attributes: true, attributeFilter: ['class'] });
  }

  // ─── Loading state para imágenes ───
  document.querySelectorAll('.img-wrapper').forEach(wrapper => {
    const img = wrapper.querySelector('img');
    if (img && !img.complete) {
      wrapper.classList.add('loading');
      img.addEventListener('load', () => {
        wrapper.classList.remove('loading');
      });
    }
  });

  // ─── Mejora de carousels ───
  document.querySelectorAll('.carousel').forEach(carousel => {
    // Pause on hover
    carousel.addEventListener('mouseenter', () => {
      const bsCarousel = bootstrap.Carousel.getInstance(carousel);
      if (bsCarousel) bsCarousel.pause();
    });
    
    carousel.addEventListener('mouseleave', () => {
      const bsCarousel = bootstrap.Carousel.getInstance(carousel);
      if (bsCarousel) bsCarousel.cycle();
    });
  });

  console.log('✨ Modas Pathy - Sistema inicializado correctamente');
});

// ─── Utilidad: Detectar si el usuario está en móvil ───
const isMobile = () => window.innerWidth <= 767;

// ─── Utilidad: Debounce para optimizar eventos ───
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// ─── Optimización de resize ───
window.addEventListener('resize', debounce(() => {
  // Aquí puedes agregar lógica específica para resize
  console.log('Window resized');
}, 250));