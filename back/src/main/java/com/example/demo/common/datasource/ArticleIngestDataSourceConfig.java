package com.example.demo.common.datasource;

import com.zaxxer.hikari.HikariDataSource;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.jdbc.autoconfigure.DataSourceProperties;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.JdbcTemplate;

import javax.sql.DataSource;

// article-ingest(배치 컨슈머)만 별도 HikariCP 풀로 분리(Bulkhead 패턴).
// 커넥션을 오래 물고 있는 배치 워크로드가 공용 풀을 잠식해서 읽기 API/다른 컨슈머가 굶는 걸 막기 위함.
//
// 원래 스프링부트가 자동 구성해주던 기본 DataSource를, 여기서 @Primary로 명시적으로 다시 정의함
// (다른 DataSource 빈이 하나라도 더 있으면 JPA 등에서 어떤 걸 써야 할지 모호해지므로, 기존 걸 명시적으로
// primary로 고정해서 나머지(JPA/기본 JdbcTemplate)는 이전과 완전히 동일하게 동작함 - 동작 변경 없음).
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
            @Qualifier("articleIngestDataSourceProperties") DataSourceProperties articleIngestDataSourceProperties) {
        return articleIngestDataSourceProperties.initializeDataSourceBuilder().type(HikariDataSource.class).build();
    }

    @Bean
    public JdbcTemplate articleIngestJdbcTemplate(@Qualifier("articleIngestDataSource") DataSource articleIngestDataSource) {
        return new JdbcTemplate(articleIngestDataSource);
    }
}
