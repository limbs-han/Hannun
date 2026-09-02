package com.example.demo.common.converter;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;

// List<String>을 JSON 컬럼(문자열)으로 저장/복원. Hibernate가 직접 인스턴스화해서 Spring Bean이 아니므로
// ObjectMapper를 주입받지 않고 여기서 직접 하나 만들어 씀 - 단순 문자열 리스트라 별도 설정 필요 없음.
@Converter
public class StringListJsonConverter implements AttributeConverter<List<String>, String> {

    private static final ObjectMapper OBJECT_MAPPER = JsonMapper.builder().build();

    @Override
    public String convertToDatabaseColumn(List<String> attribute) {
        if (attribute == null) {
            return null;
        }
        return OBJECT_MAPPER.writeValueAsString(attribute);
    }

    @Override
    public List<String> convertToEntityAttribute(String dbData) {
        if (dbData == null) {
            return null;
        }
        return OBJECT_MAPPER.readValue(dbData, OBJECT_MAPPER.getTypeFactory()
                .constructCollectionType(List.class, String.class));
    }
}
