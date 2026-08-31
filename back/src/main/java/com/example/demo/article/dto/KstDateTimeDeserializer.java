package com.example.demo.article.dto;

import tools.jackson.core.JacksonException;
import tools.jackson.core.JsonParser;
import tools.jackson.databind.DeserializationContext;
import tools.jackson.databind.deser.std.StdDeserializer;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

// 크롤러가 published를 "yyyy-MM-dd HH:mm" 형태(초/타임존 없음)로 보냄.
// 타임존 정보가 아예 없어서 서버가 임의로 가정해야 하는데, 프로젝트 전체가 Asia/Seoul(KST) 기준이라 +09:00으로 간주.
// 크롤러가 실제로 다른 타임존(UTC 등) 기준으로 보내는 거면 이 가정이 틀려서 시간이 밀릴 수 있음 - 확인 필요.
public class KstDateTimeDeserializer extends StdDeserializer<OffsetDateTime> {

    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    public KstDateTimeDeserializer() {
        super(OffsetDateTime.class);
    }

    @Override
    public OffsetDateTime deserialize(JsonParser p, DeserializationContext ctxt) throws JacksonException {
        LocalDateTime localDateTime = LocalDateTime.parse(p.getString().trim(), FORMATTER);
        return localDateTime.atOffset(ZoneOffset.ofHours(9));
    }
}
