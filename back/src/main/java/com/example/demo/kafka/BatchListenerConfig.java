package com.example.demo.kafka;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.listener.CommonErrorHandler;
import org.springframework.kafka.listener.ContainerProperties.AckMode;

/**
 * 배치로 받아야 하는 리스너 전용 컨테이너 팩토리.
 * spring.kafka.listener.type=batch 처럼 전역으로 주면 clustering-completed/search-executed
 * 리스너까지 다 배치 모드로 강제로 바뀌어버려서, 이 팩토리를 쓸 리스너에만
 * @KafkaListener(containerFactory = "batchListenerContainerFactory")로 개별 지정한다.
 */
@Configuration
public class BatchListenerConfig {

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, String> batchListenerContainerFactory(
            ConsumerFactory<String, String> consumerFactory, CommonErrorHandler kafkaErrorHandler) {
        ConcurrentKafkaListenerContainerFactory<String, String> factory = new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory);
        factory.setBatchListener(true);
        factory.setCommonErrorHandler(kafkaErrorHandler);
        factory.getContainerProperties().setAckMode(AckMode.MANUAL_IMMEDIATE);
        return factory;
    }
}
