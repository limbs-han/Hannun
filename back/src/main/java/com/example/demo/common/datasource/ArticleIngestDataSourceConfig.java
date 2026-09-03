package com.example.demo.common.datasource;

import com.zaxxer.hikari.HikariDataSource;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.jdbc.autoconfigure.DataSourceProperties;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;

@Configuration
public class ArticleIngestDataSourceConfig {

    @Primary
    @Bean
    @ConfigurationProperties("spring.datasource")
    public DataSourceProperties primaryDataSourceProperties() {
        return new DataSourceProperties();
    }

    @Primary
    @Bean
    @ConfigurationProperties("spring.datasource.hikari")
    public HikariDataSource primaryDataSource(DataSourceProperties primaryDataSourceProperties) {
        return primaryDataSourceProperties.initializeDataSourceBuilder().type(HikariDataSource.class).build();
    }

    @Bean
    @ConfigurationProperties("news.datasource.article-ingest")
    public DataSourceProperties articleIngestDataSourceProperties() {
        return new DataSourceProperties();
    }

    @Bean
    @ConfigurationProperties("news.datasource.article-ingest.hikari")
    public HikariDataSource articleIngestDataSource(
            @Qualifier("articleIngestDataSourceProperties") DataSourceProperties articleIngestDataSourceProperties,
            MeterRegistry meterRegistry) {
        HikariDataSource dataSource = articleIngestDataSourceProperties.initializeDataSourceBuilder()
                .type(HikariDataSource.class).build();
        // 스프링부트의 자동 Hikari 메트릭 바인딩은 DataSourceAutoConfiguration이 만든 기본 DataSource 하나만
        // 감지함(직접 빈으로 정의한 두 번째 DataSource는 자동 감지가 안 됨 - Spring Boot 알려진 이슈).
        // pool이 시작되기 전에 직접 MeterRegistry를 붙여서 hikaricp_* 지표가 이 풀에도 나오게 함.
        dataSource.setMetricRegistry(meterRegistry);
        return dataSource;
    }

    @Bean
    public JdbcTemplate articleIngestJdbcTemplate(@Qualifier("articleIngestDataSource") DataSource articleIngestDataSource) {
        return new JdbcTemplate(articleIngestDataSource);
    }
}
