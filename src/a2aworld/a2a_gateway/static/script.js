document.addEventListener('DOMContentLoaded', () => {
    const map = L.map('map').setView([51.505, -0.09], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    const analyzeButton = document.getElementById('analyze-button');
    const resultsDiv = document.getElementById('results');
    const spinner = document.getElementById('spinner');

    analyzeButton.addEventListener('click', () => {
        const bounds = map.getBounds();
        const bbox = {
            north: bounds.getNorth(),
            south: bounds.getSouth(),
            east: bounds.getEast(),
            west: bounds.getWest()
        };

        resultsDiv.innerHTML = '';
        spinner.style.display = 'block';
        analyzeButton.disabled = true;

        fetch('/vision/describe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(bbox)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                resultsDiv.innerHTML = `<p><strong>Error:</strong> ${data.error}</p>`;
            } else {
                resultsDiv.innerHTML = `<p>${data.description}</p>`;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            resultsDiv.innerHTML = '<p>An error occurred. Please try again.</p>';
        })
        .finally(() => {
            spinner.style.display = 'none';
            analyzeButton.disabled = false;
        });
    });
});
