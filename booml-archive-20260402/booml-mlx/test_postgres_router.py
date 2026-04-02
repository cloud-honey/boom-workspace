        models = model_registry.list_models()
        
        print(f"활성 모델: {active_model}")
        print(f"라우팅 전략: {routing_strategy.value}")
        print(f"등록된 모델: {len(models)}개")
        
        for model in models:
            status = "✅ 활성" if model["is_active"] else "⚠️ 대기"
            print(f"  {status} {model['name']} ({model['display_name']})")
        
        print("\n핫-스위칭 지원:")
        print("  - model_registry.set_active_model('모델이름')")
        print("  - model_router.set_routing_strategy(RoutingStrategy.FAST)")
        print("  - /v1/models/switch API 엔드포인트")
        
    except Exception as e:
        print(f"⚠️ 모델 라우팅 상태 확인 실패: {e}")
    
    if passed == total:
        print("\n🎉 모든 테스트 통과! PostgreSQL-first + 다중 모델 라우팅 구현 완료.")
    else:
        print(f"\n⚠️ {total - passed}개 테스트 실패. 확인이 필요합니다.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)