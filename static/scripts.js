document.addEventListener('DOMContentLoaded', () => {
    setupFavoriteForms()
})

function loadMore() {
    const urlParams = new URLSearchParams(window.location.search)
    const currentPage = parseInt(urlParams.get('page')) || 0
    const searchTerm = urlParams.get('term') || ''
    const prescriptionFilter = urlParams.get('prescription') || ''
    const maxPrice = urlParams.get('max_price') || ''
    const isAdmin = document.body.dataset.isAdmin === 'true'
    const favMeds = JSON.parse(document.body.dataset.favoriteMedications || '[]')

    fetch(`/load_more?page=${currentPage + 1}&term=${searchTerm}&prescription=${prescriptionFilter}&max_price=${maxPrice}`)
        .then(response => response.json())
        .then(data => {
            const list = document.querySelector('.medication-list')
            data.medications.forEach(m => {
                const card = document.createElement('div')
                card.className = 'medication-card' + (favMeds.includes(m.id) ? ' favorite' : '')
                card.setAttribute('data-med-id', m.id)
                let adminBlock = ''
                if (isAdmin) {
                    adminBlock = `
                        <div class="admin-buttons">
                            <form method="POST" action="/edit_medication/${m.id}" class="edit-medication-form">
                                <input type="text" name="name" value="${m.name}" required>
                                <input type="text" name="generic_name" value="${m.generic_name}" required>
                                <label>
                                    <input type="checkbox" name="prescription_only" ${m.prescription_only ? 'checked' : ''}>
                                    Только по рецепту
                                </label>
                                <input type="number" name="price" value="${m.price}" step="0.01" required>
                                <input type="number" name="quantity" value="${m.quantity}" required>
                                <button type="submit">Сохранить</button>
                            </form>
                            <form method="POST" action="/delete_medication/${m.id}" onsubmit="return confirm('Вы уверены, что хотите удалить этот препарат?');">
                                <button type="submit" class="delete-btn">Удалить</button>
                            </form>
                        </div>
                    `
                }
                card.innerHTML = `
                    <div class="medication-header">
                        <div>
                            <h3>${m.name}</h3>
                            <span class="generic-name">${m.generic_name}</span>
                        </div>
                        ${!isAdmin ? `
                            <form method="POST" action="/toggle_favorite/${m.id}" class="favorite-form">
                                <button type="submit" class="favorite-btn">
                                    ${favMeds.includes(m.id) ? '★' : '☆'}
                                </button>
                            </form>
                        ` : ''}
                    </div>
                    <div class="medication-details">
                        <p class="price">${m.price} &#8381;</p>
                        <p class="quantity">${m.quantity === 0 ? 'Отсутствует' : m.quantity + ' шт.'}</p>
                        ${m.prescription_only ? '<span class="prescription-label">Только по рецепту</span>' : ''}
                    </div>
                    ${adminBlock}
                `
                list.appendChild(card)
            })
            setupFavoriteForms()
            if (!data.has_more) {
                const btn = document.querySelector('.load-more-btn')
                if (btn) {
                    btn.style.display = 'none'
                }
            }
            urlParams.set('page', currentPage + 1)
            window.history.replaceState({}, '', `?${urlParams.toString()}`)
        })
}

function setupFavoriteForms() {
    const forms = document.querySelectorAll('.favorite-form')
    forms.forEach(f => {
        f.addEventListener('submit', async evt => {
            evt.preventDefault()
            const formData = new FormData(f)
            const action = f.getAttribute('action')
            const method = f.getAttribute('method') || 'POST'
            try {
                const resp = await fetch(action, {
                    method: method,
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                if (resp.ok) {
                    const result = await resp.json()
                    if (result.success !== undefined) {
                        const medId = parseInt(action.split('/').pop(), 10)
                        const favMeds = JSON.parse(document.body.dataset.favoriteMedications || '[]')
                        if (result.is_favorite) {
                            if (!favMeds.includes(medId)) {
                                favMeds.push(medId)
                            }
                        } else {
                            const idx = favMeds.indexOf(medId)
                            if (idx !== -1) {
                                favMeds.splice(idx, 1)
                            }
                        }
                        document.body.dataset.favoriteMedications = JSON.stringify(favMeds)
                        reorderCards()
                    }
                }
            } catch (error) {}
        })
    })
}

function reorderCards() {
    const favMeds = JSON.parse(document.body.dataset.favoriteMedications || '[]')
    const list = document.querySelector('.medication-list')
    const cards = Array.from(list.querySelectorAll('.medication-card'))
    cards.forEach(card => {
        const medId = parseInt(card.dataset.medId, 10)
        const star = card.querySelector('.favorite-btn')
        if (star) {
            star.textContent = favMeds.includes(medId) ? '★' : '☆'
        }
        if (favMeds.includes(medId)) {
            card.classList.add('favorite')
        } else {
            card.classList.remove('favorite')
        }
    })
    cards.sort((a, b) => {
        const aId = parseInt(a.dataset.medId, 10)
        const bId = parseInt(b.dataset.medId, 10)
        const aFav = favMeds.includes(aId)
        const bFav = favMeds.includes(bId)
        if (aFav && !bFav) return -1
        if (!aFav && bFav) return 1
        return 0
    })
    cards.forEach(c => list.appendChild(c))
}