// use core::arch::asm;
// TODO: Use asm template from: https://shraiwi.github.io/read.html?md=blog/simd-fast-esp32s3.md

use microfft::{real::rfft_4096, Complex32};

pub fn convert_u8_to_f32_array(data: &[u8]) -> Option<[Complex32; 4096]> {
    if data.len() != 4096 * 4 {
        return None;
    }

    // Check alignment
    let ptr = data.as_ptr();
    if ptr as usize % core::mem::align_of::<f32>() != 0 {
        return None;
    }

    let mut array = [0f32; 4096];
    for (i, chunk) in data.chunks_exact(4).enumerate() {
        array[i] = f32::from_bits(
            u32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]])
        );
    }

    Some(array)
}

pub fn compute_fft(samples: &mut [f32; 4096]) -> &mut [Complex32; 2048] {
    rfft_4096(samples)
}

// ESP32-S3 TRM has specific FFT instructions in page 60, 1.6.8 "FFT Dedicated Instructions", but they don't seem to be used here in esp-dsp code, why?
//
// https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf
//
// i.e: EE.FFT.R2BF.S16
// 
// pub fn optimised_fft() {
//     asm!(
// "dsps_fft2r_fc32_aes3_:",
// //esp_err_t dsps_fft2r_fc32_ansi(float *data, int N, float* dsps_fft_w_table_fc32)

// 	"entry	a1, 16",
// 	// Array increment for floating point data should be 4
//     // data - a2
//     // N - a3
//     // dsps_fft_w_table_fc32 - a4 - for now

//     // a6 - k, main loop counter; N2 - for (int N2 = N/2; N2 > 0; N2 >>= 1)
//     // a7 - ie
//     // a8 - j
//     // a9 - test
//     // a10 - (j*2)<<2,  or a10 - j<<3
//     // f0 - c or w[2 * j]
//     // f1 - s or w[2 * j + 1]
//     // a11 - ia
//     // a12 - m
//     // a13 - ia pointer
//     // a14 - m pointer
//     // f6  - re_temp
//     // f7  - im_temp

//     // a15 - debug

//     // This instruction are not working. Have to be fixed!!!
//     // For now theres no solution...
//     //    l32r    a4, dsps_fft_w_table_fc32_ae32
    
//     // Load shift register with 1
//     "movi.n  a5, 1",   // a5 = 1;
//     "ssr a5",          // load shift register with 1
    
//     "srli a6, a3, 1", // a6 = N2 = N/2
//     "movi a7, 1",     // a7 - ie

// ".fft2r_l1:",
//     "movi a8, 0",     // a8 - j
//     "movi a11,0",     // a11 = ia = 0;

// ".fft2r_l2:",           // loop for j, a8 - j
//         "slli    a10, a8, 3", // a10 = j<<3 // shift for cos ()   -- c = w[2 * j];
//         "add.n   a10, a10, a4", // a10 - pointer to cos
//         "EE.LDF.64.IP    f1, f0, a10, 0",

//         "movi a9, 0", // just for debug
//         "loopnez a6, .fft2r_l3",
//             "add.n    a12, a11, a6",   // a12 = m = ia + N2

//             "slli     a14, a12, 3",    // a14 - pointer for m*2
//             "slli     a13, a11, 3",    // a13 - pointer for ia*2
//             "add.n    a14, a14, a2",   // pointers to data arrays
//             "add.n    a13, a13, a2",   //
//             "EE.LDF.64.IP f5, f4, a14, 0", // data[2 * m], data[2 * m + 1]
//             "EE.LDF.64.IP f3, f2, a13, 0", // data[2 * ia], data[2 * ia + 1]

//             "mul.s    f6, f0, f4",     // re_temp =  c * data[2 * m]
//             "mul.s    f7, f0, f5",     // im_temp =  c * data[2 * m + 1]

//             "madd.s   f6, f1, f5",     // re_temp += s * data[2 * m + 1];
//             "msub.s   f7, f1, f4",     // im_temp -= s * data[2 * m];
            
//             "sub.s    f8, f2, f6",     // = data[2 * ia] - re_temp;
//             "sub.s    f9, f3, f7",     // = data[2 * ia + 1] - im_temp;

//             "add.s    f10, f2, f6",    // = data[2 * ia] + re_temp;
//             "add.s    f11, f3, f7",    // = data[2 * ia + 1] + im_temp;            
//             "EE.STF.64.IP f9, f8, a14, 0",
//             "addi     a11, a11, 1",    // ia++
//             "EE.STF.64.IP f11, f10, a13, 0",
// ".fft2r_l3:",
//         "add     a11, a11, a6",

//         "addi    a8, a8, 1",     // j++
//         "BNE     a8, a7, .fft2r_l2", // 
//     "slli    a7, a7, 1",  // ie = ie<<1
// // main loop: for (int k = N/2; k > 0; k >>= 1)
//     "srli    a6, a6, 1",  // a6 = a6>>1
//     "BNEZ    a6, .fft2r_l1",// Jump if > 0

//     "movi.n a2, 0", // return status ESP_OK
//     "retw.n"
// )
// }
