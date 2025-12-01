import logging

def calculate_position_size(capital, entry_price, stop_loss, risk_fraction=0.01, leverage=1):
    """
    Calcula tamaño de posición con gestión de riesgo avanzada
    """
    # 1. Calcular riesgo por unidad
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit == 0:
        return 0.0
    
    # 2. Calcular tamaño basado en riesgo
    risk_amount = capital * risk_fraction
    risk_based_size = risk_amount / risk_per_unit
    
    # 3. ✅ NUEVO: Ajustar riesgo según volatilidad
    volatility = risk_per_unit / entry_price
    if volatility > 0.02:  # Mercado muy volátil
        risk_fraction = min(risk_fraction, 0.005)  # Reducir riesgo a 0.5%
    
    # 4. Calcular tamaño máximo permitido por margen
    max_position_value = capital * leverage * 0.9  # 90% del margen máximo
    margin_based_size = max_position_value / entry_price
    
    # 5. Usar el MÍNIMO de ambos valores (seguridad máxima)
    final_size = min(risk_based_size, margin_based_size)
    
    # 6. Logging para diagnóstico
    if final_size < risk_based_size:
        logging.warning(
            f"⚠️ Tamaño limitado por margen | "
            f"Riesgo: {risk_based_size:.6f} | "
            f"Margen: {margin_based_size:.6f} | "
            f"Final: {final_size:.6f}"
        )
    
    return final_size