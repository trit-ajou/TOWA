import { it, describe, expect } from "vitest";
import { JPEG, PNG, GIF, WEBP, isCompressableFileType, isTransparent } from "@/definitions/image-types";
import { createMockFile } from "../mocks";

describe( "image types", () => {
    it( "should recognize the compressable file types", () => {
        expect( isCompressableFileType( PNG.mime )).toBe( false );
        expect( isCompressableFileType( GIF.mime )).toBe( false );
        expect( isCompressableFileType( JPEG.mime )).toBe( true );
        expect( isCompressableFileType( WEBP.mime )).toBe( true );
    });

    it( "should recognize the file types supporting transparency by their mime", () => {
        expect( isTransparent( createMockFile( "unimportant", PNG.mime ))).toBe( true );
        expect( isTransparent( createMockFile( "unimportant", GIF.mime ))).toBe( true );
        expect( isTransparent( createMockFile( "unimportant", JPEG.mime ))).toBe( false );
        expect( isTransparent( createMockFile( "unimportant", WEBP.mime ))).toBe( true );
    });
});
