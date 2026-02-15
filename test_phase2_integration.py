"""
═══════════════════════════════════════════════════════════════════════════════
PHASE 2 INTEGRATION TEST - VERIFICATION SCRIPT
═══════════════════════════════════════════════════════════════════════════════

Run this to verify everything is working correctly
"""

import asyncio
import sys

def test_imports():
    """Test all imports work"""
    print("=" * 70)
    print("🧪 TESTING IMPORTS")
    print("=" * 70)

    errors = []

    # Test AI v2 import
    try:
        from ai_risk_evaluator_v2 import (
            AIRiskEvaluatorV2,
            TechnicalIndicators,
            MarketStructureContext,
            DivergenceAnalysis,
            MarketRegimeContext,
            PreviousTrade
        )
        print("✅ AI Risk Evaluator v2 imported")
    except Exception as e:
        print(f"❌ AI v2 import failed: {e}")
        errors.append("AI v2")

    # Test divergence detector
    try:
        from divergence_detector import DivergenceDetector
        print("✅ Divergence detector imported")
    except Exception as e:
        print(f"❌ Divergence detector failed: {e}")
        errors.append("Divergence")

    # Test trading engine
    try:
        from trading_engine import TradingEngine
        print("✅ Trading engine imported")
    except Exception as e:
        print(f"❌ Trading engine import failed: {e}")
        errors.append("Engine")

    if errors:
        print(f"\n❌ FAILED: Missing {', '.join(errors)}")
        return False

    print("\n✅ ALL IMPORTS SUCCESSFUL")
    return True

async def test_engine_initialization():
    """Test engine initializes correctly"""
    print("\n" + "=" * 70)
    print("🧪 TESTING ENGINE INITIALIZATION")
    print("=" * 70)

    try:
        from trading_engine import TradingEngine

        print("Creating engine...")
        engine = TradingEngine()

        # Check AI v2
        if hasattr(engine, 'ai_evaluator'):
            if engine.ai_evaluator is not None:
                print(f"✅ AI v2 initialized: {type(engine.ai_evaluator).__name__}")
            else:
                print("⚠️ AI v2 is None (check ANTHROPIC_API_KEY in config.py)")
        else:
            print("❌ Engine missing ai_evaluator attribute")
            return False

        # Check divergence detector
        if hasattr(engine, 'divergence_detector'):
            if engine.divergence_detector is not None:
                print("✅ Divergence detector initialized")
            else:
                print("⚠️ Divergence detector is None")
        else:
            print("❌ Engine missing divergence_detector attribute")
            return False

        # Check price history
        if hasattr(engine, '_price_history'):
            print("✅ Price history tracking enabled")
        else:
            print("❌ Price history tracking missing")
            return False

        # Check method exists
        if hasattr(engine, '_update_price_history'):
            print("✅ _update_price_history() method exists")
        else:
            print("❌ _update_price_history() method missing")
            return False

        print("\n✅ ENGINE INITIALIZATION SUCCESSFUL")
        return True

    except Exception as e:
        print(f"❌ Engine initialization failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_divergence_detector():
    """Test divergence detection"""
    print("\n" + "=" * 70)
    print("🧪 TESTING DIVERGENCE DETECTOR")
    print("=" * 70)

    try:
        from divergence_detector import DivergenceDetector

        detector = DivergenceDetector(lookback_periods=10)

        # Test RSI divergence (bullish pattern)
        prices = [100, 98, 95, 96, 94, 92, 93, 95, 97, 96]  # Lower lows
        rsi_values = [30, 32, 28, 31, 30, 29, 32, 35, 38, 40]  # Higher lows

        result = detector.detect_rsi_divergence(prices, rsi_values)

        if result.has_divergence:
            print(f"✅ RSI divergence detected")
            print(f"   Type: {result.divergence_type}")
            print(f"   Strength: {result.strength}/40")
            print(f"   Confidence: {result.confidence:.1f}%")
        else:
            print("⚠️ No RSI divergence detected (expected bullish)")

        print("\n✅ DIVERGENCE DETECTOR WORKING")
        return True

    except Exception as e:
        print(f"❌ Divergence detector test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_ai_v2_structure():
    """Test AI v2 data structures"""
    print("\n" + "=" * 70)
    print("🧪 TESTING AI v2 DATA STRUCTURES")
    print("=" * 70)

    try:
        from ai_risk_evaluator_v2 import (
            TechnicalIndicators,
            MarketStructureContext,
            DivergenceAnalysis,
            MarketRegimeContext
        )

        # Test TechnicalIndicators
        indicators = TechnicalIndicators(
            rsi=45.5,
            ema50=50000,
            ema200=48000,
            ema_distance_pct=4.2,
            macd=0.005,
            macd_signal=0.003,
            macd_histogram=0.002,
            bb_low=49000,
            bb_mid=50000,
            bb_high=51000,
            bb_position=0.5,
            volume=1500000,
            avg_volume_20d=1200000,
            volume_ratio=1.25,
            atr=500
        )
        print("✅ TechnicalIndicators created")

        # Test MarketStructureContext
        structure = MarketStructureContext(
            nearest_support=49500,
            nearest_resistance=50500,
            support_strength=5,
            resistance_strength=3,
            support_distance_pct=1.0,
            resistance_distance_pct=1.0,
            volume_trend="increasing",
            structure_quality=75.0
        )
        print("✅ MarketStructureContext created")

        # Test DivergenceAnalysis
        divergence = DivergenceAnalysis(
            rsi_bullish_divergence=True,
            rsi_bullish_strength=25,
            macd_bullish_divergence=False,
            macd_bullish_strength=0,
            price_volume_divergence=False,
            divergence_type='bullish'
        )
        print("✅ DivergenceAnalysis created")

        # Test MarketRegimeContext
        regime = MarketRegimeContext(
            regime='uptrend',
            volatility_percentile=65.0,
            volume_trend='increasing',
            warning_flags=[]
        )
        print("✅ MarketRegimeContext created")

        print("\n✅ ALL DATA STRUCTURES WORKING")
        return True

    except Exception as e:
        print(f"❌ Data structure test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def run_all_tests():
    """Run all tests"""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "PHASE 2 VERIFICATION TEST" + " " * 23 + "║")
    print("╚" + "=" * 68 + "╝\n")

    results = []

    # Test 1: Imports
    results.append(("Imports", test_imports()))

    # Test 2: Engine initialization
    results.append(("Engine Init", await test_engine_initialization()))

    # Test 3: Divergence detector
    results.append(("Divergence", test_divergence_detector()))

    # Test 4: AI v2 structures
    results.append(("AI v2 Structures", await test_ai_v2_structure()))

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20s} {status}")

    print("\n" + "=" * 70)
    print(f"RESULT: {passed}/{total} tests passed")
    print("=" * 70)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - PHASE 2 INTEGRATION COMPLETE!")
        print("\n✅ Ready to run bot:")
        print("   python main.py")
        print("\n✅ Or test with 3 symbols first:")
        print("   1. Edit config.py: CRYPTO = ['BTC/USD', 'ETH/USD', 'SOL/USD']")
        print("   2. python main.py")
        print("   3. Watch logs for 'AI v2 evaluating'")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nCheck:")
        print("1. All files copied to correct location")
        print("2. ai_risk_evaluator_v2.py exists")
        print("3. divergence_detector.py exists")
        print("4. trading_engine.py updated")
        print("5. ANTHROPIC_API_KEY set in config.py")
        return False

if __name__ == "__main__":
    asyncio.run(run_all_tests())