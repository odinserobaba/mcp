"""Тесты для анализатора селекторов"""
import pytest
from src.agents.selector_analyzer import AdaptiveSelectorAnalyzer

@pytest.mark.asyncio
async def test_analyze_angular_page():
    """Тест анализа Angular страницы"""
    html = """
    <input formcontrolname="email" type="email" placeholder="Email">
    <button type="submit">Войти</button>
    """

    analysis = await AdaptiveSelectorAnalyzer.analyze_page_structure(html)

    assert 'Angular' in analysis['detected_frameworks']
    assert analysis['page_stats']['total_inputs'] > 0
    assert analysis['page_stats']['total_buttons'] > 0

@pytest.mark.asyncio
async def test_find_email_selectors():
    """Тест поиска селекторов для email"""
    page_analysis = {
        'input_fields': [{
            'attributes': {'formcontrolname': 'email', 'type': 'email'},
            'selector_suggestions': ['[formcontrolname="email"]']
        }]
    }

    selectors = AdaptiveSelectorAnalyzer.find_best_selector_for_action(
        'fill', 'email', page_analysis
    )

    assert len(selectors) > 0
    assert any('email' in s for s in selectors)
