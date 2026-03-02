document.addEventListener("DOMContentLoaded", () => {
  // --- Smooth Scrolling for Navigation ---
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute("href"));
      if (target) {
        window.scrollTo({
          top: target.offsetTop - 100,
          behavior: "smooth",
        });
      }
    });
  });

  // --- GitHub Releases Fetcher ---
  const fetchReleases = async () => {
    const releasesList = document.getElementById("releases-list");
    if (!releasesList) return;

    try {
      const response = await fetch(
        "https://api.github.com/repos/giuseppe99barchetta/SuggestArr/releases",
      );
      if (!response.ok) throw new Error("Failed to fetch releases");
      const releases = await response.json();

      // Clear skeleton
      releasesList.innerHTML = "";

      // Limit to the last 3 releases
      const latestReleases = releases.slice(0, 3);

      latestReleases.forEach((release, index) => {
        const date = new Date(release.published_at).toLocaleDateString(
          undefined,
          {
            year: "numeric",
            month: "long",
            day: "numeric",
          },
        );

        const releaseCard = document.createElement("div");
        releaseCard.className = "release-card";
        releaseCard.innerHTML = `
          <div class="release-header">
            <div class="release-version">
              ${release.tag_name}
              <i class="fas fa-chevron-down release-chevron"></i>
            </div>
            <span class="release-date">${date}</span>
          </div>
          <div class="release-content">
            <div class="release-body">
              ${marked.parse(release.body || "No release notes available.")}
            </div>
            <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border);">
              <a href="${release.html_url}" target="_blank" class="btn btn-secondary" style="padding: 0.5rem 1rem; font-size: 0.75rem;">
                <i class="fab fa-github"></i> View on GitHub
              </a>
            </div>
          </div>
        `;

        releaseCard.addEventListener("click", () => {
          releaseCard.classList.toggle("active");
        });

        releasesList.appendChild(releaseCard);
      });
    } catch (error) {
      console.error("Error fetching releases:", error);
      releasesList.innerHTML =
        '<p style="color: #ef4444;">Could not load recent releases. <a href="https://github.com/giuseppe99barchetta/SuggestArr/releases" target="_blank" style="color: inherit; text-decoration: underline;">See them on GitHub</a>.</p>';
    }
  };

  fetchReleases();

  // --- Animation on Scroll (Intersection Observer) ---
  const animateOnScroll = () => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.style.opacity = "1";
            entry.target.style.transform = "translateY(0)";
          }
        });
      },
      { threshold: 0.1 },
    );

    document
      .querySelectorAll(".feature-card, .step, .section-title")
      .forEach((el) => {
        el.style.opacity = "0";
        el.style.transform = "translateY(20px)";
        el.style.transition = "all 0.6s cubic-bezier(0.22, 1, 0.36, 1)";
        observer.observe(el);
      });
  };

  animateOnScroll();
});
