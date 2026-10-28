import pytest
import pandas as pd
import numpy as np
from src.interpolate_curve import calculate_curves, to_long_format

# Фикстуры для чтения данных
@pytest.fixture
def moex_points():
    # Загружаем реальные точки MOEX (берем из data/)
    raw = pd.read_csv('data/gcurve_2026-07-31_moex.csv', sep=';', header=1, decimal=',')
    cols = [c for c in raw.columns if c.startswith('period_')]
    points = sorted((float(c.split('_')[1]), float(raw.loc[0, c])) for c in cols)
    return [p for p in points if p[0] <= 20]

@pytest.fixture
def expected_data():
    # Ожидаемые значения из Excel
    return pd.read_csv('tests/fixtures/curve_2026-07-31_expected.csv', sep=';')

def test_base_curve_matches_excel(moex_points, expected_data):
    """ТЕСТ ИЗ ТЗ: Проверяем, что базовая кривая совпадает с эталоном из Excel."""
    result_df = calculate_curves(moex_points)
    
    # Сравниваем базовые ставки
    for index, expected_row in expected_data.iterrows():
        tenor = expected_row['тенор']
        expected_rate = expected_row['ставка']
        
        # Находим эту же строку в нашем результате
        actual_row = result_df[result_df['тенор'] == tenor].iloc[0]
        actual_rate = actual_row['Ставка_БС']
        
        # Сравниваем с точностью до 4 знаков
        assert np.isclose(actual_rate, expected_rate, atol=1e-4), \
            f"Несовпадение для тенора {tenor}: Python {actual_rate} != Excel {expected_rate}"

def test_long_format_shape(moex_points):
    """Проверяем, что длинный формат имеет правильное количество строк (19*7 = 133)."""
    wide_df = calculate_curves(moex_points)
    long_df = to_long_format(wide_df)
    
    assert len(long_df) == 133, "Длинная таблица должна содержать 133 строки"
    assert 'scenario_id' in long_df.columns
    assert 'discount_factor' in long_df.columns


def test_long_format_method_values(moex_points):
    """Значения method в длинном формате совпадают с допустимыми в базе (curve_point)."""
    long_df = to_long_format(calculate_curves(moex_points))

    assert set(long_df['method']) == {'moex', 'nearest', 'interpolation', 'extrapolation'}
