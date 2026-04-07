// Global Search Script for Europe Incoming FIT Packages
// This script enables searching across all packages from any page

let allPackages = [];
let searchResults = [];

// Load packages data
async function loadPackages() {
    try {
        const depth = getPageDepth();
        const jsonPath = depth + 'packages.json';
        const response = await fetch(jsonPath);
        const data = await response.json();
        allPackages = data.packages;
    } catch (error) {
        console.error('Error loading packages:', error);
    }
}

// Determine page depth for correct relative paths
// Works for any repo name — no hardcoded site name
function getPageDepth() {
    const path = window.location.pathname;
    // Remove leading/trailing slashes, split into parts
    // parts[0] = repo name (e.g. FITStandard, FITPremium)
    // parts[1+] = subfolders (e.g. multi-country, scandinavia-iceland)
    const parts = path.replace(/^\//, '').replace(/\/$/, '').split('/');
    const subParts = parts.slice(1).filter(Boolean);
    const depth = subParts.length;
    if (depth === 0) return './';
    if (depth === 1) return '../';
    if (depth === 2) return '../../';
    return '../../../';
}

// Search function
function searchPackages(query) {
    if (!query || query.length < 2) {
        return [];
    }

    const searchTerm = query.toLowerCase().trim();
    const results = [];

    allPackages.forEach(pkg => {
        let score = 0;
        let matchedFields = [];

        // Check package name (highest priority)
        if (pkg.name && pkg.name.toLowerCase().includes(searchTerm)) {
            score += 10;
            matchedFields.push('name');
        }

        // Check description
        if (pkg.description && pkg.description.toLowerCase().includes(searchTerm)) {
            score += 7;
            matchedFields.push('description');
        }

        // Check cities
        if (pkg.cities) {
            pkg.cities.forEach(city => {
                if (city.toLowerCase().includes(searchTerm)) {
                    score += 8;
                    if (!matchedFields.includes('city')) matchedFields.push('city');
                }
            });
        }

        // Check region
        if (pkg.region && pkg.region.toLowerCase().includes(searchTerm)) {
            score += 6;
            matchedFields.push('region');
        }

        // Check tags
        if (pkg.tags) {
            pkg.tags.forEach(tag => {
                if (tag.toLowerCase().includes(searchTerm)) {
                    score += 5;
                    if (!matchedFields.includes('tag')) matchedFields.push('tag');
                }
            });
        }

        // Check tour type — guard against null
        if (pkg.type && pkg.type.toLowerCase().includes(searchTerm)) {
            score += 4;
            matchedFields.push('type');
        }

        // Check duration — guard against null
        if (pkg.duration && pkg.duration.toLowerCase().includes(searchTerm)) {
            score += 3;
            matchedFields.push('duration');
        }

        if (score > 0) {
            results.push({
                ...pkg,
                score: score,
                matchedFields: matchedFields
            });
        }
    });

    // Sort by score (highest first)
    results.sort((a, b) => b.score - a.score);

    return results;
}

// Display search results
function displaySearchResults(results) {
    const depth = getPageDepth();

    let resultsContainer = document.getElementById('globalSearchResults');

    if (!resultsContainer) {
        resultsContainer = document.createElement('div');
        resultsContainer.id = 'globalSearchResults';
        resultsContainer.className = 'search-results-overlay';
        document.body.appendChild(resultsContainer);
    }

    if (results.length === 0) {
        resultsContainer.innerHTML = `
            <div class="search-results-container">
                <div class="search-results-header">
                    <h3>Search Results</h3>
                    <button onclick="closeSearchResults()" class="close-btn">✕</button>
                </div>
                <div class="no-results">
                    <p>No packages found matching your search.</p>
                </div>
            </div>
        `;
        resultsContainer.style.display = 'block';
        return;
    }

    const resultsHTML = results.map(pkg => {
        const citiesList = pkg.cities && pkg.cities.length ? pkg.cities.join(', ') : '—';
        const pdfUrl = depth + pkg.folder + '/' + pkg.filename;
        const priceStr = pkg.price_twin ? `From ${pkg.currency || '€'}${pkg.price_twin.toLocaleString()} pp` : '';
        const typeStr = pkg.type || '';
        const durationStr = pkg.duration || '';

        return `
            <a href="${pdfUrl}" class="search-result-card" target="_blank">
                <div class="result-header">
                    <h4>${pkg.name}</h4>
                    <span class="pdf-badge">PDF</span>
                </div>
                <div class="result-details">
                    <span class="result-region">${pkg.region}</span>
                    ${durationStr ? `<span class="result-separator">•</span><span class="result-duration">${durationStr}</span>` : ''}
                    ${typeStr ? `<span class="result-separator">•</span><span class="result-type">${typeStr}</span>` : ''}
                    ${priceStr ? `<span class="result-separator">•</span><span class="result-price">${priceStr}</span>` : ''}
                </div>
                ${pkg.description ? `<div class="result-desc">${pkg.description}</div>` : ''}
                <div class="result-cities">
                    <strong>Cities:</strong> ${citiesList}
                </div>
            </a>
        `;
    }).join('');

    resultsContainer.innerHTML = `
        <div class="search-results-container">
            <div class="search-results-header">
                <h3>Search Results <span class="result-count">(${results.length})</span></h3>
                <button onclick="closeSearchResults()" class="close-btn">✕</button>
            </div>
            <div class="search-results-list">
                ${resultsHTML}
            </div>
        </div>
    `;

    resultsContainer.style.display = 'block';
}

// Close search results
function closeSearchResults() {
    const resultsContainer = document.getElementById('globalSearchResults');
    if (resultsContainer) {
        resultsContainer.style.display = 'none';
    }
}

// Initialize global search on page load
document.addEventListener('DOMContentLoaded', async function() {
    await loadPackages();

    const searchBox = document.getElementById('searchBox');
    if (searchBox) {
        let searchTimeout;

        searchBox.addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            const query = e.target.value;
            if (query.length < 2) {
                closeSearchResults();
                return;
            }
            searchTimeout = setTimeout(() => {
                const results = searchPackages(query);
                displaySearchResults(results);
            }, 300);
        });

        // Close results when clicking outside
        document.addEventListener('click', function(e) {
            const resultsContainer = document.getElementById('globalSearchResults');
            if (resultsContainer &&
                !resultsContainer.contains(e.target) &&
                e.target !== searchBox) {
                closeSearchResults();
            }
        });

        // Prevent closing when clicking inside results
        document.addEventListener('click', function(e) {
            if (e.target.closest('.search-results-container')) {
                e.stopPropagation();
            }
        });
    }
});

// Add CSS for search results overlay
const searchStyles = `
<style>
.search-results-overlay {
    position: fixed;
    top: 80px;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 9999;
    display: none;
    overflow-y: auto;
    padding: 20px;
}

.search-results-container {
    max-width: 900px;
    margin: 0 auto;
    background: white;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    overflow: hidden;
}

.search-results-header {
    padding: 24px;
    background: #f5f5f5;
    border-bottom: 1px solid #e0e0e0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.search-results-header h3 {
    margin: 0;
    font-size: 1.4em;
    color: #212121;
}

.result-count {
    color: #757575;
    font-size: 0.9em;
    font-weight: 400;
}

.close-btn {
    background: none;
    border: none;
    font-size: 1.5em;
    color: #757575;
    cursor: pointer;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: all 0.2s;
}

.close-btn:hover {
    background: #e0e0e0;
    color: #212121;
}

.search-results-list {
    padding: 16px;
    max-height: 600px;
    overflow-y: auto;
}

.search-result-card {
    display: block;
    padding: 20px;
    margin-bottom: 12px;
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    text-decoration: none;
    color: inherit;
    transition: all 0.2s;
}

.search-result-card:hover {
    border-color: #2196F3;
    box-shadow: 0 4px 12px rgba(33, 150, 243, 0.15);
    transform: translateY(-2px);
}

.result-header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    margin-bottom: 8px;
}

.result-header h4 {
    margin: 0;
    font-size: 1.1em;
    color: #212121;
    font-weight: 600;
}

.pdf-badge {
    background: #d32f2f;
    color: white;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 0.75em;
    font-weight: 600;
    letter-spacing: 0.5px;
    flex-shrink: 0;
    margin-left: 12px;
}

.result-details {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    font-size: 0.9em;
    color: #757575;
    flex-wrap: wrap;
}

.result-separator { color: #bdbdbd; }

.result-price {
    color: #2e7d32;
    font-weight: 600;
}

.result-desc {
    font-size: 0.88em;
    color: #666;
    font-style: italic;
    margin: 6px 0;
    line-height: 1.4;
}

.result-cities {
    font-size: 0.9em;
    color: #616161;
    margin-top: 8px;
}

.result-cities strong { color: #424242; }

.no-results {
    padding: 60px 20px;
    text-align: center;
}

.no-results p {
    color: #757575;
    font-size: 1.1em;
}

@media (max-width: 768px) {
    .search-results-overlay {
        padding: 0;
        top: 140px;
    }
    .search-results-container {
        border-radius: 0;
        min-height: 100%;
    }
    .result-header {
        flex-direction: column;
        gap: 8px;
    }
    .result-details { flex-wrap: wrap; }
}
</style>
`;

// Inject styles into page
document.head.insertAdjacentHTML('beforeend', searchStyles);
