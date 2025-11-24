(function () {
  const main = document.getElementById("mainImage");
  const thumbs = document.querySelectorAll(".thumb-img");
  const lightbox = document.getElementById("lightbox");
  const lightImg = document.getElementById("lightboxImg");
  const closeBtn = lightbox ? lightbox.querySelector(".btn-close") : null;

  // Cambiar imagen principal al hacer click en miniaturas
  thumbs.forEach((img) => {
    img.addEventListener("click", () => {
      thumbs.forEach(t => t.classList.remove("active"));
      img.classList.add("active");
      const src = img.getAttribute("src");
      if (main) {
        main.classList.add("img-switching");
        main.addEventListener("load", () => {
        main.classList.remove("img-switching");
      }, { once: true });

      main.src = src;
      main.dataset.zoom = src;
}

    });
  });

  // Abrir lightbox al hacer click en la imagen principal
  if (main && lightbox && lightImg) {
    main.addEventListener("click", () => {
      const src = main.dataset.zoom || main.src;
      lightImg.src = src;
      lightbox.classList.remove("d-none");
      document.body.style.overflow = "hidden";
    });
  }

  // Cerrar lightbox
  function closeLightbox() {
    lightbox.classList.add("d-none");
    document.body.style.overflow = "";
    lightImg.removeAttribute("src");
  }
  if (closeBtn) closeBtn.addEventListener("click", closeLightbox);
  if (lightbox) {
    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) closeLightbox();
    });
    document.addEventListener("keyup", (e) => {
      if (e.key === "Escape" && !lightbox.classList.contains("d-none")) {
        closeLightbox();
      }
    });
  }
})();
