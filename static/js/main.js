// 1. Draw the category chart on the dashboard (data comes from /chart-data/)
async function drawCategoryChart() {
  const canvas = document.getElementById("categoryChart");
  if (!canvas) return;

  const url = `${canvas.dataset.url}?month=${canvas.dataset.month}`;
  try {
    const response = await fetch(url);
    const data = await response.json();

    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: data.labels,
        datasets: [{ data: data.values }],
      },
      options: { plugins: { legend: { position: "bottom" } } },
    });
  } catch (error) {
    console.error("Could not load chart data:", error);
  }
}

// 2. Fade out success/error messages after 4 seconds
function autoHideMessages() {
  document.querySelectorAll(".message").forEach((msg) => {
    setTimeout(() => {
      msg.style.opacity = "0";
      setTimeout(() => msg.remove(), 500);
    }, 4000);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  drawCategoryChart();
  autoHideMessages();
});
