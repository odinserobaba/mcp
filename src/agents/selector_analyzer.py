"""Анализатор селекторов страницы"""
import re
from typing import Dict, List
from bs4 import BeautifulSoup
from src.utils.logger import logger

class AdaptiveSelectorAnalyzer:
    """Анализирует HTML и находит оптимальные селекторы"""

    @staticmethod
    async def analyze_page_structure(page_text: str) -> Dict:
        """Анализ структуры страницы"""
        analysis = {
            'input_fields': [],
            'buttons': [],
            'links': [],
            'detected_frameworks': [],
            'page_stats': {}
        }

        try:
            soup = BeautifulSoup(page_text, 'lxml')
        except:
            soup = BeautifulSoup(page_text, 'html.parser')

        # Определение фреймворков
        frameworks = {
            'Angular': ['ng-', 'mat-', 'formcontrolname', 'cdk-'],
            'React': ['data-react', 'react-', 'className='],
            'Vue': ['v-', 'vue-', '__vue__'],
        }

        page_lower = page_text.lower()
        for framework, markers in frameworks.items():
            if any(marker in page_lower for marker in markers):
                analysis['detected_frameworks'].append(framework)

        # Анализ input полей
        for input_tag in soup.find_all(['input', 'textarea']):
            attrs = input_tag.attrs
            selectors = AdaptiveSelectorAnalyzer._generate_selectors_from_attrs(attrs)

            if selectors:
                analysis['input_fields'].append({
                    'tag': input_tag.name,
                    'attributes': attrs,
                    'selector_suggestions': selectors
                })

        # Анализ кнопок
        for button in soup.find_all(['button', 'a']):
            text = button.get_text(strip=True)
            if text and len(text) > 1:
                analysis['buttons'].append({
                    'text': text,
                    'selector': f'text="{text}"',
                    'tag': button.name
                })

        analysis['page_stats'] = {
            'total_inputs': len(analysis['input_fields']),
            'total_buttons': len(analysis['buttons']),
            'frameworks': list(set(analysis['detected_frameworks']))
        }

        logger.info(f"Анализ завершен: {analysis['page_stats']}")
        return analysis

    @staticmethod
    def _generate_selectors_from_attrs(attrs: Dict) -> List[str]:
        """Генерирует селекторы из атрибутов"""
        selectors = []

        priority_attrs = [
            'data-cy', 'data-testid', 'data-qa', 'data-test',
            'formcontrolname', 'name', 'id', 'placeholder',
            'aria-label', 'type'
        ]

        for attr_name in priority_attrs:
            value = attrs.get(attr_name)
            if value:
                if attr_name.startswith('data-'):
                    selectors.append(f'[{attr_name}="{value}"]')
                elif attr_name == 'formcontrolname':
                    selectors.append(f'[formcontrolname="{value}"]')
                    selectors.append(f'input[formcontrolname="{value}"]')
                elif attr_name == 'name':
                    selectors.append(f'[name="{value}"]')
                elif attr_name == 'id':
                    selectors.append(f'#{value}')

        return selectors[:5]

    @staticmethod
    def find_best_selector_for_action(action_type: str, target: str,
                                     page_analysis: Dict) -> List[str]:
        """Находит лучшие селекторы для действия"""
        suggestions = []
        target_lower = target.lower()

        if action_type in ['fill', 'type']:
            for field in page_analysis.get('input_fields', []):
                score = 0
                attrs = field.get('attributes', {})

                for attr_value in attrs.values():
                    if target_lower in str(attr_value).lower():
                        score += 3

                if score > 0 and 'selector_suggestions' in field:
                    suggestions.extend(field['selector_suggestions'])

        elif action_type in ['click', 'press']:
            for button in page_analysis.get('buttons', []):
                button_text = button.get('text', '').lower()
                if target_lower in button_text:
                    suggestions.append(button['selector'])

        # Убираем дубликаты
        return list(dict.fromkeys(suggestions))[:5]
